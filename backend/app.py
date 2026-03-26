from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

from .services_sesami import get_sesami_status, parse_upload as parse_sesami_upload, run_workflow as run_sesami_workflow
from .services_zeopp import detect_zeopp_binary, run_workflow as run_zeopp_workflow

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / 'dist'
ARTIFACTS_DIR = ROOT / 'backend_artifacts'
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

UNSET = object()
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()

app = Flask(__name__)


def create_job(workflow: str, filename: str) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    job_dir = ARTIFACTS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    job = {
        'jobId': job_id,
        'workflow': workflow,
        'filename': filename,
        'status': 'queued',
        'progress': 0,
        'stage': 'queued',
        'result': None,
        'error': None,
        'warning': None,
        'createdAt': time.time(),
        'updatedAt': time.time(),
        '_jobDir': str(job_dir),
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    return job


def serialize_job(job: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in job.items() if not key.startswith('_')}


def get_job(job_id: str) -> dict[str, Any] | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return None
        return serialize_job(job)


def current_progress(job_id: str) -> int:
    with JOBS_LOCK:
        job = JOBS[job_id]
        return int(job.get('progress', 0))


def advance_job(job_id: str, stage: str, progress: int) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        current = int(job.get('progress', 0))
        next_progress = max(current, int(progress))
        if next_progress != current or job.get('stage') != stage:
            job['progress'] = next_progress
            job['stage'] = stage
            if job.get('status') == 'queued':
                job['status'] = 'running'
            job['updatedAt'] = time.time()


def finish_job(
    job_id: str,
    *,
    status: str,
    result: Any = UNSET,
    error: Any = UNSET,
    warning: Any = UNSET,
) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job['status'] = status
        job['stage'] = status
        job['progress'] = 100
        if result is not UNSET:
            job['result'] = result
        if error is not UNSET:
            job['error'] = error
        if warning is not UNSET:
            job['warning'] = warning
        job['updatedAt'] = time.time()


def fail_job(job_id: str, error: str, warning: str | None = None) -> None:
    finish_job(job_id, status='failed', error=error, warning=warning)


def sesami_worker(
    job_id: str,
    data,
    gas: str,
    version: str,
    mode: str,
    advanced: dict[str, Any],
) -> None:
    job_dir = ARTIFACTS_DIR / job_id
    try:
        result = run_sesami_workflow(
            job_id,
            job_dir,
            data,
            gas,
            version,
            mode,
            advanced,
            lambda stage, progress: advance_job(job_id, stage, progress),
        )
        finish_job(job_id, status='completed', result=result, warning=result.get('warning'))
    except Exception as exc:
        fail_job(job_id, str(exc))


def zeopp_worker(job_id: str, input_path: Path, mode: str, params: dict[str, Any]) -> None:
    job_dir = ARTIFACTS_DIR / job_id
    try:
        result = run_zeopp_workflow(
            job_id,
            job_dir,
            input_path,
            mode,
            params,
            lambda stage, progress: advance_job(job_id, stage, progress),
            lambda: current_progress(job_id),
        )
        finish_job(job_id, status='completed', result=result, warning=result.get('warning'))
    except Exception as exc:
        fail_job(job_id, str(exc))


def get_advanced_options(form) -> dict[str, Any]:
    return {
        'r2Cutoff': form.get('r2Cutoff'),
        'r2Min': form.get('r2Min'),
        'dpi': form.get('dpi'),
        'fontSize': form.get('fontSize'),
        'fontType': form.get('fontType'),
        'legend': form.get('legend'),
    }


def start_sesami_job(mode: str):
    upload = request.files.get('file')
    gas = request.form.get('gas', 'Argon')
    version = request.form.get('version', '2.9')

    if gas not in {'Argon', 'Nitrogen'}:
        return jsonify({'error': 'Unsupported gas. Choose Argon or Nitrogen.'}), 400
    if version not in {'2.9', '1.0'}:
        return jsonify({'error': 'Unsupported SESAMI version. Choose 2.9 or 1.0.'}), 400
    if mode in {'bet-esw', 'betml'} and version != '2.9':
        return jsonify({'error': 'This SESAMI mode is only available in version 2.9.'}), 400
    if upload is None or not upload.filename:
        return jsonify({'error': 'Please upload a CSV or AIF file.'}), 400

    raw_bytes = upload.read()
    try:
        data = parse_sesami_upload(upload.filename, raw_bytes)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400

    job = create_job(f'sesami:{mode}', upload.filename)
    job_dir = ARTIFACTS_DIR / job['jobId']
    (job_dir / upload.filename).write_bytes(raw_bytes)

    worker = threading.Thread(
        target=sesami_worker,
        args=(job['jobId'], data, gas, version, mode, get_advanced_options(request.form)),
        daemon=True,
    )
    worker.start()
    return jsonify(serialize_job(job)), 202


def start_zeopp_job(mode: str):
    zeopp_binary, zeopp_message = detect_zeopp_binary()
    if zeopp_binary is None:
        return jsonify({'error': zeopp_message}), 503

    upload = request.files.get('file')
    if upload is None or not upload.filename:
        return jsonify({'error': 'Please upload a structure file.'}), 400

    raw_bytes = upload.read()
    job = create_job(f'zeopp:{mode}', upload.filename)
    job_dir = ARTIFACTS_DIR / job['jobId']
    input_path = job_dir / upload.filename
    input_path.write_bytes(raw_bytes)

    params = {
        'chanRadius': request.form.get('chanRadius'),
        'probeRadius': request.form.get('probeRadius'),
        'numSamples': request.form.get('numSamples'),
        'extended': request.form.get('extended'),
    }

    worker = threading.Thread(
        target=zeopp_worker,
        args=(job['jobId'], input_path, mode, params),
        daemon=True,
    )
    worker.start()
    return jsonify(serialize_job(job)), 202


@app.get('/api/health')
def health() -> Any:
    sesami_ready, sesami_message = get_sesami_status()
    zeopp_binary, zeopp_message = detect_zeopp_binary()
    return jsonify(
        {
            'status': 'ok',
            'sesamiReady': sesami_ready,
            'sesamiMessage': sesami_message,
            'zeoppReady': zeopp_binary is not None,
            'zeoppMessage': zeopp_message,
        }
    )


@app.get('/api/zeopp/status')
def zeopp_status() -> Any:
    zeopp_binary, zeopp_message = detect_zeopp_binary()
    return jsonify(
        {
            'available': zeopp_binary is not None,
            'binaryPath': str(zeopp_binary) if zeopp_binary else None,
            'message': zeopp_message,
        }
    )


@app.get('/api/jobs/<job_id>')
def job_status(job_id: str) -> Any:
    job = get_job(job_id)
    if job is None:
        return jsonify({'error': 'Job not found.'}), 404
    return jsonify(job)


@app.post('/api/sesami/bet')
def sesami_bet() -> Any:
    return start_sesami_job('bet')


@app.post('/api/sesami/bet-esw')
def sesami_bet_esw() -> Any:
    return start_sesami_job('bet-esw')


@app.post('/api/sesami/betml')
def sesami_betml() -> Any:
    return start_sesami_job('betml')


@app.post('/api/sesami/compare')
def sesami_compare() -> Any:
    return start_sesami_job('compare')


@app.post('/api/zeopp/psd')
def zeopp_psd() -> Any:
    return start_zeopp_job('psd')


@app.post('/api/zeopp/res')
def zeopp_res() -> Any:
    return start_zeopp_job('res')


@app.post('/api/zeopp/chan')
def zeopp_chan() -> Any:
    return start_zeopp_job('chan')


@app.post('/api/zeopp/sa')
def zeopp_sa() -> Any:
    return start_zeopp_job('sa')


@app.post('/api/zeopp/vol')
def zeopp_vol() -> Any:
    return start_zeopp_job('vol')


@app.post('/api/zeopp/volpo')
def zeopp_volpo() -> Any:
    return start_zeopp_job('volpo')


@app.get('/api/artifacts/<job_id>/<path:filename>')
def artifacts(job_id: str, filename: str) -> Any:
    return send_from_directory(ARTIFACTS_DIR / job_id, filename)


@app.get('/')
def index() -> Any:
    if DIST_DIR.exists():
        return send_from_directory(DIST_DIR, 'index.html')
    return jsonify({'error': 'Frontend build not found. Run npm run build first.'}), 503


@app.get('/assets/<path:filename>')
def frontend_assets(filename: str) -> Any:
    return send_from_directory(DIST_DIR / 'assets', filename)


@app.get('/<path:filename>')
def frontend_root_assets(filename: str) -> Any:
    target = DIST_DIR / filename
    if target.is_file():
        return send_from_directory(DIST_DIR, filename)
    return jsonify({'error': 'Not found'}), 404


if __name__ == '__main__':
    port = int(os.getenv('CHEMEX_PORT', '8000'))
    app.run(host='127.0.0.1', port=port, debug=False)


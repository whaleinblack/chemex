from __future__ import annotations

import json
import threading
import time
from collections import deque
from pathlib import Path

from flask import jsonify, request

from .services_research import MAX_IMAGE_BYTES, identify, image_data, research, research_status

SLOTS = threading.BoundedSemaphore(2)
STARTS = deque()
RATE_LOCK = threading.Lock()


def register_research_routes(app, create_job, advance_job, finish_job, fail_job):
    @app.get('/api/research/status')
    def status():
        return jsonify(research_status())

    def launch(action, inputs):
        # Bound paid calls and public-database requests across clients per process.
        with RATE_LOCK:
            now = time.monotonic()
            while STARTS and STARTS[0] < now - 3600:
                STARTS.popleft()
            if len(STARTS) >= 30:
                return jsonify({'error': '文献检索已达每小时请求上限，请稍后重试。 / Research limit reached; retry later.'}), 429
            if not SLOTS.acquire(blocking=False):
                return jsonify({'error': '检索服务繁忙，请稍后重试。 / Research service is busy; retry later.'}), 429
            STARTS.append(now)
        job = create_job(f'research:{action}', 'monomer-combination')

        def worker():
            try:
                progress = lambda stage, value: advance_job(job['jobId'], stage, value)
                if action == 'identify':
                    result = identify(inputs, progress)
                else:
                    result = research(inputs['monomers'], inputs['notes'], inputs['locale'], progress)
                filename = 'identity.json' if action == 'identify' else 'research.json'
                (Path(job['_jobDir']) / filename).write_text(json.dumps(result, ensure_ascii=False, indent=2))
                finish_job(job['jobId'], status='completed', result=result)
            except Exception as exc:
                fail_job(job['jobId'], str(exc))
            finally:
                SLOTS.release()
        threading.Thread(target=worker, daemon=True).start()
        return jsonify({key: value for key, value in job.items() if not key.startswith('_')}), 202

    @app.post('/api/research/identify')
    def identify_route():
        request.max_content_length = 22 * 1024 * 1024
        try:
            rows = json.loads(request.form.get('monomers', '[]'))
            if not isinstance(rows, list) or not 2 <= len(rows) <= 4:
                raise ValueError('请提供 2–4 个单体。 / Provide 2–4 monomers.')
            inputs = []
            for index, row in enumerate(rows):
                if not isinstance(row, dict) or not isinstance(row.get('text', ''), str):
                    raise ValueError('Invalid monomer input.')
                text = row.get('text', '').strip()
                if len(text) > 500:
                    raise ValueError('每个单体名称最多 500 字符。 / Maximum 500 characters per monomer.')
                upload = request.files.get(f'image{index}')
                image = image_data(upload.read(MAX_IMAGE_BYTES + 1)) if upload else None
                if not text and not image:
                    raise ValueError('每个单体需要名称、CAS 或结构图片。 / Each monomer needs a name, CAS, or image.')
                if image and not research_status()['vision']:
                    raise ValueError('图片识别尚未配置；请移除图片并填写名称或 CAS。 / Image recognition is not configured; enter a name or CAS without an image.')
                inputs.append({'text': text, 'image': image})
            return launch('identify', inputs)
        except (ValueError, TypeError) as exc:
            return jsonify({'error': str(exc)}), 400

    @app.post('/api/research/search')
    def search_route():
        request.max_content_length = 32 * 1024
        body = request.get_json(silent=True)
        try:
            if not isinstance(body, dict) or body.get('confirmed') is not True:
                raise ValueError('请先确认单体身份。 / Confirm monomer identities first.')
            rows = body.get('monomers')
            if not isinstance(rows, list) or not 2 <= len(rows) <= 4:
                raise ValueError('请提供 2–4 个单体。 / Provide 2–4 monomers.')
            monomers = []
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError('Invalid monomer input.')
                name = row.get('name', '')
                if not isinstance(name, str) or not name.strip() or len(name) > 500:
                    raise ValueError('请确认每个单体的完整名称。 / Confirm each full monomer name.')
                aliases = row.get('aliases', [])
                if not isinstance(aliases, list) or len(aliases) > 12 or any(not isinstance(a, str) or len(a) > 500 for a in aliases):
                    raise ValueError('Invalid monomer aliases.')
                monomer = {'name': name.strip(), 'aliases': aliases}
                for key in ('cas', 'backbone'):
                    value = row.get(key) or ''
                    if not isinstance(value, str) or len(value) > 500:
                        raise ValueError('Invalid monomer identity.')
                    monomer[key] = value
                monomers.append(monomer)
            notes = body.get('notes', '')
            if not isinstance(notes, str) or len(notes) > 2000:
                raise ValueError('补充要求最多 2000 字符。 / Maximum 2000 characters for notes.')
            return launch('search', {'monomers': monomers, 'notes': notes,
                                     'locale': 'en' if body.get('locale') == 'en' else 'zh'})
        except (ValueError, TypeError) as exc:
            return jsonify({'error': str(exc)}), 400

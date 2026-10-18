"""Generate small, original regression EPUBs without distributing users' books.

Usage: python scripts/make-epubreader-fixtures.py <output-directory>
Open the resulting files through the reader's normal file picker.
"""
from pathlib import Path
import sys
from urllib.parse import quote
from zipfile import ZipFile, ZIP_DEFLATED


def make(directory, name, *, encoded=False, fixed=False):
    filename = "('chapter.xhtml',)" if encoded else 'chapter.xhtml'
    href = quote(filename, safe='')
    metadata = '<meta property="rendition:layout">pre-paginated</meta>' if fixed else ''
    title = ('Fixed image' if fixed else 'Encoded chapter' if encoded else 'Nested navigation and typography')
    with ZipFile(directory / (name + '.epub'), 'w', compression=ZIP_DEFLATED) as z:
        z.writestr('mimetype', 'application/epub+zip', compress_type=0)
        z.writestr('META-INF/container.xml', '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="OPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr('OPS/book.opf', f'''<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">chemex-regression-{name}</dc:identifier><dc:title>{title}</dc:title><dc:creator>Reader regression fixtures</dc:creator><dc:language>en</dc:language>{metadata}</metadata><manifest><item id="nav" href="navigation/nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="chapter" href="text/{href}" media-type="application/xhtml+xml"/><item id="css" href="styles/main.css" media-type="text/css"/><item id="import" href="styles/nested.css" media-type="text/css"/><item id="image" href="images/page.svg" media-type="image/svg+xml"/></manifest><spine><itemref idref="chapter"/></spine></package>''')
        z.writestr('OPS/navigation/nav.xhtml', f'''<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head><body><nav epub:type="toc"><ol><li><a href="../text/{href}#start">Regression chapter</a></li></ol></nav></body></html>''')
        z.writestr('OPS/styles/main.css', '@import "nested.css"; p { font-size:18px!important; line-height:24px!important; }')
        z.writestr('OPS/styles/nested.css', '.proof { color: rgb(17, 34, 51); }')
        z.writestr('OPS/images/page.svg', '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" viewBox="0 0 600 800"><rect width="600" height="800" fill="#dfcbaa"/><circle cx="300" cy="400" r="150" fill="#914936"/></svg>')
        content = '<img src="../images/page.svg" alt="Original regression graphic" style="width:100%;height:100%"/>' if fixed else ''.join('<p class="proof" style="font-size:18px!important"><span style="font-size:18px!important">Original regression paragraph. Changing font size must change these glyphs; changing line spacing must preserve their font size.</span></p>' for _ in range(30))
        z.writestr('OPS/text/' + filename, f'''<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title><meta name="viewport" content="width=600, height=800"/><link rel="stylesheet" href="../styles/main.css"/></head><body id="start">{'' if fixed else '<h1>Regression chapter</h1>'}{content}</body></html>''')


if __name__ == '__main__':
    target = Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    make(target, 'typography')
    make(target, 'encoded', encoded=True)
    make(target, 'fixed', fixed=True)

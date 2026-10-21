"""Generate small, original regression EPUBs without distributing users' books.

Usage: python scripts/make-epubreader-fixtures.py <output-directory>
Open the resulting files through the reader's normal file picker.
"""
from pathlib import Path
import sys
from urllib.parse import quote
from zipfile import ZipFile, ZIP_DEFLATED


def make(directory, name, *, encoded=False, fixed=False, vertical=False, constrained=False, hanging=False):
    filename = "('chapter.xhtml',)" if encoded else 'constrained.xhtml' if constrained else 'chapter.xhtml'
    href = quote(filename, safe='')
    metadata = '<meta property="rendition:layout">pre-paginated</meta>' if fixed else ''
    title = ('Japanese vertical' if vertical else 'Fixed image' if fixed else 'Encoded chapter' if encoded else 'Nested navigation and typography')
    with ZipFile(directory / (name + '.epub'), 'w', compression=ZIP_DEFLATED) as z:
        z.writestr('mimetype', 'application/epub+zip', compress_type=0)
        z.writestr('META-INF/container.xml', '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="OPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr('OPS/book.opf', f'''<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">chemex-regression-{name}</dc:identifier><dc:title>{title}</dc:title><dc:creator>Reader regression fixtures</dc:creator><dc:language>{'ja' if vertical else 'en'}</dc:language>{metadata}</metadata><manifest><item id="nav" href="navigation/nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="chapter" href="text/{href}" media-type="application/xhtml+xml"/>{'<item id="second" href="text/second.xhtml" media-type="application/xhtml+xml"/>' if vertical else ''}{'<item id="constrained" href="styles/constrained.css" media-type="text/css"/>' if constrained else ''}<item id="css" href="styles/main.css" media-type="text/css"/><item id="import" href="styles/nested.css" media-type="text/css"/><item id="image" href="images/page.svg" media-type="image/svg+xml"/></manifest><spine {'page-progression-direction="rtl"' if vertical else ''}><itemref idref="chapter"/>{'<itemref idref="second"/>' if vertical else ''}</spine></package>''')
        z.writestr('OPS/navigation/nav.xhtml', f'''<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head><body><nav epub:type="toc"><ol><li><a href="../text/{href}#start">Regression chapter</a></li>{'<li><a href="../text/second.xhtml#start">Second Japanese chapter</a></li>' if vertical else ''}</ol></nav></body></html>''')
        z.writestr('OPS/styles/main.css', '@import "nested.css"; p { font-size:18px!important; line-height:24px!important; }')
        z.writestr('OPS/styles/nested.css', '.proof { color: rgb(17, 34, 51); }'+('html,body,.proof,.proof span {writing-mode:vertical-rl!important;-webkit-writing-mode:vertical-rl!important;text-orientation:upright} ruby{ruby-position:over}' if vertical else '')+('.hanging{ text-indent:-3em; padding-block-start:3em; margin-inline-start:-1em; } .hanging a {text-indent:inherit}' if hanging else ''))
        if constrained:
            z.writestr('OPS/styles/constrained.css','body{width:1200px!important;min-width:1200px!important;height:440px!important;overflow:hidden!important;padding:90px!important;columns:2!important;column-gap:20px!important} .pagebox{width:1000px;height:300px;overflow:hidden;columns:2;position:relative} .proof{white-space:nowrap!important}')
        z.writestr('OPS/images/page.svg', '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" viewBox="0 0 600 800"><rect width="600" height="800" fill="#dfcbaa"/><circle cx="300" cy="400" r="150" fill="#914936"/></svg>')
        content = '<img src="../images/page.svg" alt="Original regression graphic" style="width:100%;height:100%"/>' if fixed else ''.join('<p class="proof" style="font-size:18px!important"><span style="font-size:18px!important">Original regression paragraph. Changing font size must change these glyphs; changing line spacing must preserve their font size.</span></p>' for _ in range(30))
        if vertical:content=''.join('<p class="proof"><span style="writing-mode:vertical-rl!important">これは横書き切り替えを確かめるための文章です。<ruby>日本語<rt>にほんご</rt></ruby>を読みながら、次の頁へ進みます。朝の光が窓から入り、静かな部屋で本を開きました。</span></p>' for _ in range(65))
        if hanging:
            content='<h1>目次</h1>'+''.join('<p class="hanging"><a href="#dialogue">第'+str(i)+'章　試験用の部屋</a></p>' for i in range(1,5))+'<h2 id="dialogue">人物の対話</h2>'+''.join('<p class="hanging proof">'+('甲者' if i%2 else '乙者')+'　これは表示を確かめるための対話です。名前も本文も欠けずに読むことができます。'+('静かな部屋で、本の次の頁を開きました。'*3)+'</p>' for i in range(50))
        if constrained:content='<div class="pagebox">'+content.replace('<span style=', '<a href="#start"><span style=').replace('</span></p>','</span></a></p>')+'</div>'
        z.writestr('OPS/text/' + filename, f'''<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title><meta name="viewport" content="width=600, height=800"/><link rel="stylesheet" href="../styles/main.css"/>{'<link rel="stylesheet" href="../styles/constrained.css"/>' if constrained else ''}</head><body id="start" {'style="width:1100px!important;height:300px!important;overflow:hidden!important"' if constrained else ''}>{'' if fixed else '<h1>Regression chapter</h1>'}{content}</body></html>''')

        if vertical:z.writestr('OPS/text/second.xhtml',z.read('OPS/text/'+filename).decode().replace('Regression chapter','第二章'))


if __name__ == '__main__':
    target = Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    make(target, 'typography')
    make(target, 'encoded', encoded=True)
    make(target, 'fixed', fixed=True)
    make(target, 'japanese-vertical', vertical=True)
    make(target, 'japanese-constrained', vertical=True, constrained=True)
    make(target, 'japanese-hanging', vertical=True, hanging=True)

"""
Minimal pure-Python PDF generator for test fixtures.
Generates valid standard PDF 1.4 files without any external dependencies.
"""
from pathlib import Path

def create_pdf(pages_content, width=612, height=792):
    """
    pages_content: list of lists of text lines or dicts with text and coordinates:
      [{'text': str, 'x': float, 'y': float, 'size': float}] or stream string.
    """
    objects = []
    
    # Obj 1: Catalog
    # Obj 2: Pages
    num_pages = len(pages_content)
    page_obj_ids = [3 + i * 2 for i in range(num_pages)]
    font_obj_id = 3 + num_pages * 2
    
    # 1: Catalog
    catalog = f"<< /Type /Catalog /Pages 2 0 R >>"
    objects.append(catalog)
    
    # 2: Pages
    kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    pages = f"<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>"
    objects.append(pages)
    
    # Pages and Contents
    for i, content in enumerate(pages_content):
        page_id = page_obj_ids[i]
        content_id = page_id + 1
        
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {width} {height}] "
            f"/Resources << /Font << /F1 {font_obj_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        objects.append(page_dict)
        
        if isinstance(content, str):
            stream_data = content
        else:
            stream_lines = ["BT", "/F1 12 Tf"]
            for item in content:
                x = item.get('x', 50)
                y = item.get('y', 700)
                size = item.get('size', 12)
                text = item.get('text', '')
                # Replace unicode bullet with octal escape for PDF Type1
                text = text.replace('\u2022', '\\225').replace('(', '\\(').replace(')', '\\)')
                stream_lines.append(f"/F1 {size} Tf")
                stream_lines.append(f"1 0 0 1 {x} {y} Tm")
                stream_lines.append(f"({text}) Tj")
            stream_lines.append("ET")
            stream_data = "\n".join(stream_lines)
            
        stream_bytes = stream_data.encode('latin1', errors='replace')
        content_dict = f"<< /Length {len(stream_bytes)} >>\nstream\n{stream_data}\nendstream"
        objects.append(content_dict)
        
    # Font with WinAnsiEncoding for proper bullet support
    font = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    objects.append(font)
    
    # Assemble PDF
    out = ["%PDF-1.4\n%\\xe2\\xe3\\xcf\\xd3\n"]
    offsets = [0]
    
    for i, obj in enumerate(objects, 1):
        offsets.append(len("".join(out).encode('latin1')))
        out.append(f"{i} 0 obj\n{obj}\nendobj\n")
        
    xref_offset = len("".join(out).encode('latin1'))
    out.append(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.append(f"{offset:010d} 00000 n \n")
        
    out.append(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n")
    return "".join(out).encode('latin1')

def generate_all_fixtures(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Single-column multiple paragraphs
    single_col_items = [
        {'text': 'First paragraph begins here with introductory information.', 'x': 50, 'y': 720, 'size': 12},
        {'text': 'It continues onto a second line in the same paragraph.', 'x': 50, 'y': 704, 'size': 12},
        {'text': 'Here is the concluding line of this first block of text.', 'x': 50, 'y': 688, 'size': 12},
        
        {'text': 'Second paragraph introduces separate conceptual material.', 'x': 50, 'y': 640, 'size': 12},
        {'text': 'This paragraph explores detailed behavior and edge cases.', 'x': 50, 'y': 624, 'size': 12},
        {'text': 'Closing remarks for paragraph two.', 'x': 50, 'y': 608, 'size': 12},
        
        {'text': 'Third paragraph wraps up the single column document.', 'x': 50, 'y': 560, 'size': 12},
        {'text': 'Everything aligns in a clean, vertical reading sequence.', 'x': 50, 'y': 544, 'size': 12},
    ]
    (output_dir / "single_column.pdf").write_bytes(create_pdf([single_col_items]))
    
    # 2. Two-column document
    two_col_items = [
        # Full-width header
        {'text': 'Two Column Analysis and Technical Demonstration', 'x': 50, 'y': 730, 'size': 16},
        
        # Column 1 (Left, x=50 to 260)
        {'text': 'Column one line one text.', 'x': 50, 'y': 680, 'size': 11},
        {'text': 'Column one line two text.', 'x': 50, 'y': 664, 'size': 11},
        {'text': 'Column one line three text.', 'x': 50, 'y': 648, 'size': 11},
        {'text': 'Column one line four text.', 'x': 50, 'y': 632, 'size': 11},
        {'text': 'Column one line five text.', 'x': 50, 'y': 616, 'size': 11},
        
        # Column 2 (Right, x=330 to 550, gutter between 260 and 330)
        {'text': 'Column two line one text.', 'x': 340, 'y': 680, 'size': 11},
        {'text': 'Column two line two text.', 'x': 340, 'y': 664, 'size': 11},
        {'text': 'Column two line three text.', 'x': 340, 'y': 648, 'size': 11},
        {'text': 'Column two line four text.', 'x': 340, 'y': 632, 'size': 11},
        {'text': 'Column two line five text.', 'x': 340, 'y': 616, 'size': 11},
        
        # Full-width footer
        {'text': 'Page 1 Footer Information across columns', 'x': 50, 'y': 50, 'size': 10},
    ]
    (output_dir / "two_column.pdf").write_bytes(create_pdf([two_col_items]))
    
    # 3. Lists
    list_items = [
        {'text': 'Items to review for verification:', 'x': 50, 'y': 720, 'size': 12},
        {'text': '1. First numbered requirement with details', 'x': 50, 'y': 690, 'size': 11},
        {'text': 'continuation of first requirement', 'x': 70, 'y': 675, 'size': 11},
        {'text': '2. Second numbered item in list sequence', 'x': 50, 'y': 650, 'size': 11},
        {'text': '3. Third numbered item with sub-points', 'x': 50, 'y': 625, 'size': 11},
        {'text': '• First bulleted item in unordered section', 'x': 50, 'y': 590, 'size': 11},
        {'text': '• Second bulleted point with extra remarks', 'x': 50, 'y': 565, 'size': 11},
        {'text': '• Third bulleted point to finish', 'x': 50, 'y': 540, 'size': 11},
    ]
    (output_dir / "lists.pdf").write_bytes(create_pdf([list_items]))
    
    # 4. Hyphenated line endings
    hyphen_items = [
        {'text': 'This document illustrates how inter-', 'x': 50, 'y': 720, 'size': 12},
        {'text': 'action between complex multi-', 'x': 50, 'y': 704, 'size': 12},
        {'text': 'disciplinary systems requires well-', 'x': 50, 'y': 688, 'size': 12},
        {'text': 'designed interfaces.', 'x': 50, 'y': 672, 'size': 12},
    ]
    (output_dir / "hyphenated.pdf").write_bytes(create_pdf([hyphen_items]))
    
    # 5. Multi-page (3 pages)
    p1 = [
        {'text': 'Multi-page document - Page 1 content', 'x': 50, 'y': 720, 'size': 14},
        {'text': 'Paragraph on page one with introductory content.', 'x': 50, 'y': 690, 'size': 11},
    ]
    p2 = [
        {'text': 'Multi-page document - Page 2 content', 'x': 50, 'y': 720, 'size': 14},
        {'text': 'Continuing text on page two across boundary.', 'x': 50, 'y': 690, 'size': 11},
    ]
    p3 = [
        {'text': 'Multi-page document - Page 3 content', 'x': 50, 'y': 720, 'size': 14},
        {'text': 'Final page summary and concluding text.', 'x': 50, 'y': 690, 'size': 11},
    ]
    (output_dir / "multipage.pdf").write_bytes(create_pdf([p1, p2, p3]))

    # 5b. Multi-page bounded performance fixtures (20 pages and 50 pages)
    pages_20 = [
        [
            {'text': f'Document Benchmark Section - Page {i + 1}', 'x': 50, 'y': 720, 'size': 14},
            {'text': f'Paragraph line 1 on page {i + 1} with standard text content.', 'x': 50, 'y': 690, 'size': 11},
            {'text': f'Paragraph line 2 on page {i + 1} continuing with details.', 'x': 50, 'y': 674, 'size': 11},
            {'text': f'Page {i + 1} Footer Marker', 'x': 50, 'y': 50, 'size': 10},
        ]
        for i in range(20)
    ]
    (output_dir / "multipage_20.pdf").write_bytes(create_pdf(pages_20))

    pages_50 = [
        [
            {'text': f'Document Benchmark Section - Page {i + 1}', 'x': 50, 'y': 720, 'size': 14},
            {'text': f'Paragraph line 1 on page {i + 1} with standard text content.', 'x': 50, 'y': 690, 'size': 11},
            {'text': f'Paragraph line 2 on page {i + 1} continuing with details.', 'x': 50, 'y': 674, 'size': 11},
            {'text': f'Page {i + 1} Footer Marker', 'x': 50, 'y': 50, 'size': 10},
        ]
        for i in range(50)
    ]
    (output_dir / "multipage_50.pdf").write_bytes(create_pdf(pages_50))
    
    # 6. Scanned/Textless PDF (vector graphics/image only, NO BT/ET or Tj)
    # Draws a rectangle and circle with PDF graphics operators, no text
    graphics_stream = (
        "0.2 0.4 0.8 rg\n"
        "50 600 200 150 re\n"
        "f\n"
        "0.8 0.2 0.2 RG\n"
        "3 w\n"
        "300 600 200 150 re\n"
        "S\n"
    )
    (output_dir / "scanned_textless.pdf").write_bytes(create_pdf([graphics_stream]))
    print(f"Generated 6 PDF fixtures in {output_dir}")

if __name__ == '__main__':
    generate_all_fixtures(Path('/home/colvyn/Documents/Projects/vortex/tests/fixtures/pdf'))

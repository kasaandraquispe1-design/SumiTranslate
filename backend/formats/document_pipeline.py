from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backend.core.languages import language_name
from backend.protection.math_protector import ProtectedElement, protect_text, restore_markers
from backend.processing.word_counter import count_words
from backend.validation.validator import validate

TranslateFn = Callable[[str], str]
MARKER_RE = re.compile(r"\[\[[A-Z]+_\d{3}\]\]")
SEGMENT_RE = re.compile(r"\[\[SUMIRE_SEG_(\d{6})_(START|END)\]\]")

@dataclass
class PDFTextBlock:
    page: int
    bbox: tuple[float, float, float, float]
    text: str
    fontsize: float
    flags: int
    color: int
    kind: str = "text"

def _markers(text: str) -> list[str]:
    return MARKER_RE.findall(text)

def _prompt(source_lang: str, target_lang: str, segments: list[tuple[str, str]]) -> str:
    body=[]
    for sid,text in segments:
        body += [f"[[SUMIRE_SEG_{sid}_START]]", text, f"[[SUMIRE_SEG_{sid}_END]]"]
    return f"""You are a professional academic and scientific document translator.
Translate from {language_name(source_lang)} to {language_name(target_lang)}.
Each segment is one visual paragraph, heading, caption or table cell. Translate only natural language inside it.
STRICT RULES:
1. Preserve every SUMIRE_SEG START/END marker exactly and in order.
2. Preserve every protected marker exactly, including MATH, NUMBER, TABLE, CODE, URL and CITE markers.
3. Never translate or alter formulas, variables, numbers, symbols, code, URLs, citations or protected structure.
4. Never merge segments or move text between segments/cells.
5. Output only the translated segments. No explanations.
SEGMENTS:
{chr(10).join(body)}
OUTPUT ONLY THE TRANSLATION."""

def _extract_segment_parts(translated: str, expected_ids: list[str]) -> dict[str,str]:
    matches=list(SEGMENT_RE.finditer(translated)); parts={}; cursor=0; k=0
    for sid in expected_ids:
        if k+1 >= len(matches): raise RuntimeError(f"La traducción fue bloqueada: falta el segmento {sid}.")
        a,b=matches[k],matches[k+1]
        if a.group(1)!=sid or a.group(2)!="START": raise RuntimeError(f"La traducción fue bloqueada: el segmento {sid} está fuera de orden.")
        if b.group(1)!=sid or b.group(2)!="END": raise RuntimeError(f"La traducción fue bloqueada: el segmento {sid} no tiene un cierre válido.")
        if a.start()<cursor: raise RuntimeError("La traducción fue bloqueada: los segmentos se solaparon.")
        parts[sid]=translated[a.end():b.start()].strip("\n"); cursor=b.end(); k+=2
    if k!=len(matches): raise RuntimeError("La traducción fue bloqueada: Gemini añadió segmentos estructurales.")
    return parts

def _multiset(items:list[str])->dict[str,int]:
    d={}
    for x in items: d[x]=d.get(x,0)+1
    return d

def _translate_segments(segments:list[tuple[str,str]], source_lang:str, target_lang:str, translate_fn:TranslateFn)->tuple[list[str],dict]:
    if not segments: return [],{"passed":True,"checked":0,"issues":[]}
    prepared=[]; originals={}
    for sid,text in segments:
        protected,store,_=protect_text(text); prepared.append((sid,protected,store)); originals[sid]=text
    translated=translate_fn(_prompt(source_lang,target_lang,[(sid,p) for sid,p,_ in prepared]))
    if not translated or not str(translated).strip(): raise RuntimeError("La traducción fue bloqueada: Gemini no devolvió contenido.")
    parts=_extract_segment_parts(str(translated).strip(),[sid for sid,_,_ in prepared])
    outputs=[]; issues=[]
    for sid,protected,store in prepared:
        part=parts[sid]
        if _multiset(_markers(part))!=_multiset(_markers(protected)):
            issues.append({"segment":sid,"type":"protected_marker_changed"}); continue
        restored=restore_markers(part,store)
        check=validate(originals[sid],restored,store,protected_source=protected,translated_protected=part)
        if not check["passed"]: issues.append({"segment":sid,"issues":check["issues"]}); continue
        outputs.append(restored)
    if issues:
        ids=", ".join(str(x.get("segment")) for x in issues[:5])
        raise RuntimeError(f"La traducción fue bloqueada por la validación estructural del documento. Segmentos: {ids}")
    return outputs,{"passed":True,"checked":len(outputs),"issues":[]}

def _aggregate_counts(texts:list[str])->dict:
    total=translatable=protected=protected_words=0; by_type={}
    for text in texts:
        c=count_words(text); total+=int(c.get("total",0)); translatable+=int(c.get("translatable",0)); protected+=int(c.get("protected",0)); protected_words+=int(c.get("protectedWords",0))
        for kind,n in c.get("protectedByType",{}).items(): by_type[kind]=by_type.get(kind,0)+int(n)
    return {"total":total,"translatable":translatable,"protected":protected,"protectedWords":protected_words,"protectedRatio":protected_words/total if total else 0,"protectedByType":dict(sorted(by_type.items()))}

def _block_text(block:dict)->str:
    return "\n".join("".join(str(s.get("text","")) for s in line.get("spans",[])).rstrip() for line in block.get("lines",[])).strip()

def _inside(rect,region)->bool:
    cx=(rect[0]+rect[2])/2; cy=(rect[1]+rect[3])/2
    return region.x0<=cx<=region.x1 and region.y0<=cy<=region.y1

def _table_cell_rect(table,ri,ci,rows,cols):
    import pymupdf
    cells=list(getattr(table,"cells",[]) or []); idx=ri*cols+ci
    if 0<=idx<len(cells) and cells[idx] is not None:
        r=pymupdf.Rect(cells[idx])
        if r.width>0 and r.height>0: return r
    b=pymupdf.Rect(table.bbox); w=b.width/max(cols,1); h=b.height/max(rows,1)
    return pymupdf.Rect(b.x0+ci*w,b.y0+ri*h,b.x0+(ci+1)*w,b.y0+(ri+1)*h)

def _extract_pdf_blocks(doc)->list[PDFTextBlock]:
    import pymupdf
    blocks=[]; regions_by_page={}
    for pi,page in enumerate(doc):
        regions=[]
        try: tables=list(getattr(page.find_tables(),"tables",[]) or [])
        except Exception: tables=[]
        for table in tables:
            data=table.extract() or []; rows=len(data); cols=max((len(r) for r in data),default=0)
            if not cols: continue
            for ri,row in enumerate(data):
                for ci in range(cols):
                    value=row[ci] if ci<len(row) else None
                    if value is None or not str(value).strip(): continue
                    r=_table_cell_rect(table,ri,ci,rows,cols)
                    clip=page.get_text("dict",clip=r,sort=True)
                    spans=[s for b in clip.get("blocks",[]) for l in b.get("lines",[]) for s in l.get("spans",[]) if s.get("text")]
                    first=spans[0] if spans else {}
                    blocks.append(PDFTextBlock(pi,(float(r.x0),float(r.y0),float(r.x1),float(r.y1)),str(value).strip(),float(first.get("size",9) or 9),int(first.get("flags",0) or 0),int(first.get("color",0) or 0),"table_cell"))
            try: regions.append(pymupdf.Rect(table.bbox))
            except Exception: pass
        regions_by_page[pi]=regions
    for pi,page in enumerate(doc):
        for block in page.get_text("dict",sort=True).get("blocks",[]):
            if block.get("type")!=0 or not block.get("lines"): continue
            text=_block_text(block)
            if not text: continue
            bbox=tuple(float(x) for x in block["bbox"])
            if any(_inside(bbox,r) for r in regions_by_page.get(pi,[])): continue
            spans=[s for l in block.get("lines",[]) for s in l.get("spans",[]) if s.get("text")]
            if not spans: continue
            first=spans[0]; blocks.append(PDFTextBlock(pi,bbox,text,float(first.get("size",10) or 10),int(first.get("flags",0) or 0),int(first.get("color",0) or 0)))
    blocks.sort(key=lambda b:(b.page,b.bbox[1],b.bbox[0])); return blocks

def _font(flags:int)->str:
    bold=bool(flags&16); italic=bool(flags&2)
    return "figbi" if bold and italic else "figbo" if bold else "figit" if italic else "figo"

def _insert_pdf(page,rect,text,block):
    color=(((block.color>>16)&255)/255,((block.color>>8)&255)/255,(block.color&255)/255); size=max(5.0,min(block.fontsize,24.0))
    while size>=4:
        rc=page.insert_textbox(rect,text,fontname=_font(block.flags),fontsize=size,color=color,overlay=True)
        if rc>=0:return
        size-=0.5
    raise RuntimeError("La reconstrucción PDF fue bloqueada: el texto traducido no cabe en su región original.")

def _validate_final_pdf(output:bytes,rendered_blocks)->dict:
    import pymupdf
    result=pymupdf.open(stream=output,filetype="pdf"); extracted=[p.get_text("text") for p in result]; checked=0; warnings=[]
    for block,_ in rendered_blocks:
        _,store,_=protect_text(block.text); page_text=extracted[block.page] if block.page<len(extracted) else ""
        for item in store.values():
            checked+=1; original=re.sub(r"\s+","",item.original)
            if original and original not in re.sub(r"\s+","",page_text): warnings.append({"type":"protected_content_not_extractable","page":block.page+1,"kind":item.type})
    pages=len(extracted); result.close(); return {"passed":True,"checked":checked,"issues":warnings[:20],"renderedPages":pages}

def translate_pdf_document(path: str|Path,source_lang:str,target_lang:str,translate_fn:TranslateFn,*,batch_size:int=18):
    try: import pymupdf
    except ImportError as exc: raise RuntimeError("Falta PyMuPDF. Declara pymupdf en requirements.txt.") from exc
    source=pymupdf.open(str(path))
    try:
        blocks=_extract_pdf_blocks(source)
        if not blocks: raise RuntimeError("Este PDF no contiene texto seleccionable. Para PDF escaneados necesitamos OCR.")
        originals=[b.text for b in blocks]; translated_by_index={}
        # TABLE FIX: translate every cell independently, never as a batch.
        for i,b in enumerate(blocks):
            if b.kind!="table_cell": continue
            outs,_=_translate_segments([(f"{i+1:06d}",b.text)],source_lang,target_lang,translate_fn)
            if len(outs)!=1: raise RuntimeError(f"La traducción de la celda de tabla {i+1} no produjo un resultado válido.")
            translated_by_index[i]=outs[0]
        # Keep normal paragraphs batched for speed/cost.
        normal=[i for i,b in enumerate(blocks) if b.kind!="table_cell"]
        for start in range(0,len(normal),batch_size):
            ids=normal[start:start+batch_size]; outs,_=_translate_segments([(f"{i+1:06d}",blocks[i].text) for i in ids],source_lang,target_lang,translate_fn)
            if len(outs)!=len(ids): raise RuntimeError("La traducción no produjo todos los bloques normales del PDF.")
            for i,v in zip(ids,outs): translated_by_index[i]=v
        translated_texts=[translated_by_index[i] for i in range(len(blocks))]
        for b in blocks: source[b.page].add_redact_annot(pymupdf.Rect(b.bbox),fill=False,cross_out=False)
        for page in source: page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,text=pymupdf.PDF_REDACT_TEXT_REMOVE)
        rendered=[]
        for b,translated in zip(blocks,translated_texts):
            page=source[b.page]; r=pymupdf.Rect(b.bbox)
            r=pymupdf.Rect(r.x0+1,r.y0+.5,r.x1-1,r.y1+.5) if b.kind=="table_cell" else pymupdf.Rect(r.x0,r.y0-.5,r.x1,r.y1+max(1,b.fontsize*.18))
            _insert_pdf(page,r,translated,b); rendered.append((b,translated))
        output=source.tobytes(garbage=4,deflate=True,clean=True); validation=_validate_final_pdf(output,rendered)
        return output,{"format":"pdf","pages":len(set(b.page for b in blocks)),"textBlocks":len(blocks),"counts":_aggregate_counts(originals),"validation":validation}
    finally: source.close()

def _run_has_drawing(run)->bool:
    try:return bool(run._r.xpath(".//*[local-name()='drawing' or local-name()='pict' or local-name()='object']"))
    except Exception:return False

def _iter_table_paragraphs(table):
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs: yield p
            for nested in cell.tables: yield from _iter_table_paragraphs(nested)

def _paragraphs_in_document(document):
    seen=set()
    def emit(p):
        key=id(p._p)
        if key not in seen: seen.add(key); yield p
    for p in document.paragraphs: yield from emit(p)
    for table in document.tables:
        for p in _iter_table_paragraphs(table): yield from emit(p)
    for section in document.sections:
        for part in (section.header,section.first_page_header,section.even_page_header,section.footer,section.first_page_footer,section.even_page_footer):
            for p in part.paragraphs: yield from emit(p)
            for table in part.tables:
                for p in _iter_table_paragraphs(table): yield from emit(p)

def _replace_paragraph_text_preserving_drawings(paragraph,value:str):
    text_runs=[r for r in paragraph.runs if not _run_has_drawing(r)]
    if not text_runs:return
    text_runs[0].text=value
    for r in text_runs[1:]:r.text=""

def translate_docx_document(path: str|Path,source_lang:str,target_lang:str,translate_fn:TranslateFn):
    try: from docx import Document
    except ImportError as exc: raise RuntimeError("Falta python-docx. Declara python-docx en requirements.txt.") from exc
    document=Document(str(path)); locations=[]; originals=[]
    for p in _paragraphs_in_document(document):
        text=p.text.strip()
        if text: locations.append(p); originals.append(text)
    translated=[]
    for start in range(0,len(originals),18):
        batch=originals[start:start+18]; outs,_=_translate_segments([(f"{i:06d}",t) for i,t in enumerate(batch,start=start+1)],source_lang,target_lang,translate_fn); translated.extend(outs)
    for p,value in zip(locations,translated): _replace_paragraph_text_preserving_drawings(p,value)
    output_path=Path(path).with_name(f"{Path(path).stem}_sumire_temp.docx")
    try: document.save(str(output_path)); output=output_path.read_bytes()
    finally:
        try: output_path.unlink()
        except OSError: pass
    return output,{"format":"docx","textBlocks":len(originals),"counts":_aggregate_counts(originals),"validation":{"passed":True,"checked":len(originals),"issues":[]},"translatedText":"\n\n".join(translated)}

def translate_document(path: str|Path,source_lang:str,target_lang:str,translate_fn:TranslateFn):
    suffix=Path(path).suffix.lower()
    if suffix==".pdf": return translate_pdf_document(path,source_lang,target_lang,translate_fn)
    if suffix==".docx": return translate_docx_document(path,source_lang,target_lang,translate_fn)
    raise ValueError(f"Formato de documento no soportado: {suffix or '(sin extensión)'}")

from __future__ import annotations
import json, re
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parents[1] / 'order_forms'
FILES = [
    '1st Aid Order Form.pdf','84 Lumber.pdf','Advantage-Makita.pdf','Alumax.pdf','Amazon.pdf',
    'BF Walls & Accessories (1).pdf','Basco.pdf','Facilities and Warehouse Supplies.pdf','Ferguson.pdf',
    'Fleet.pdf','Grainger.pdf','Home Depot Lumber.pdf',"Lowe's Tools and Lumber.pdf",'Lumber Order Sheet Test.pdf',
    'MSC.pdf','PPE Order Form.pdf','RF Fager (1).pdf','Sales Kit-Corp Order Only.pdf','Seachrome (1).pdf',
    'TB Philly.pdf','Van Supplies.pdf','Zoe.pdf'
]

FORM_META = {
    '1st Aid Order Form.pdf': ('first-aid','First Aid Order Form','Corporate Purchasing'),
    '84 Lumber.pdf': ('84-lumber','84 Lumber Order Form','84 Lumber'),
    'Advantage-Makita.pdf': ('advantage-makita','Advantage / Makita Order Form','Advantage / Scott Electric'),
    'Alumax.pdf': ('alumax','Alumax Order Form','Alumax'),
    'Amazon.pdf': ('amazon','Amazon Order Form','Amazon'),
    'BF Walls & Accessories (1).pdf': ('bf-walls','BF Walls & Accessories Order Form','Bath Fitter Corporate'),
    'Basco.pdf': ('basco','Basco Order Form','Basco'),
    'Facilities and Warehouse Supplies.pdf': ('facilities','Facilities Supplies Order Form','Corporate Purchasing'),
    'Ferguson.pdf': ('ferguson','Ferguson Order Form','Ferguson'),
    'Fleet.pdf': ('fleet','Fleet Order Form','Corporate Purchasing'),
    'Grainger.pdf': ('grainger','Grainger Order Form','Grainger'),
    'Home Depot Lumber.pdf': ('home-depot','Home Depot Order Form','Home Depot'),
    "Lowe's Tools and Lumber.pdf": ('lowes','Lowe\'s Order Form',"Lowe's"),
    'Lumber Order Sheet Test.pdf': ('lumber-combined','Lumber Order Form','Lumber Vendor Choice'),
    'MSC.pdf': ('msc','MSC Order Form','MSC'),
    'PPE Order Form.pdf': ('ppe','PPE Order Form','Corporate Purchasing'),
    'RF Fager (1).pdf': ('rf-fager','RF Fager Order Form','RF Fager'),
    'Sales Kit-Corp Order Only.pdf': ('sales-kit','Sales Supply Order Form','Bath Fitter Corporate'),
    'Seachrome (1).pdf': ('seachrome','SeaChrome Order Form','SeaChrome'),
    'TB Philly.pdf': ('tb-philly','TB Philly Order Form','TB Philly'),
    'Van Supplies.pdf': ('van-supplies','Van Supplies Order Form','Corporate Purchasing'),
    'Zoe.pdf': ('zoe','Zoe Order Form','Zoe'),
}

FORM_WARNINGS = {
    '84-lumber': ['84 Lumber form excludes IBS.'],
    'advantage-makita': ['Internal transfer from Corporate is required for this form.'],
    'alumax': ['Alumax has a $750 shipping minimum.'],
    'bf-walls': ['Use this form for items not ordered straight to the job.'],
    'basco': ['Place on office order day.', 'Basco has a $750 shipping minimum.'],
    'fleet': ['Code Fleet orders to 655-4135.', 'Fleet form is for one each per van or warehouse supply.'],
    'ppe': ['Internal transfer from Corporate is required for this form.'],
    'sales-kit': ['Corporate order only.'],
    'seachrome': ['SeaChrome has a $1,500 minimum order for shipping.'],
    'tb-philly': ['TB Philly has a $2,500 minimum order for shipping.'],
    'zoe': ['Zoe form is for service items only.'],
}

ALIASES = [
    (re.compile(r'\bRF\s*Fager\b',re.I),'RF Fager'),
    (re.compile(r'\bGrainger\b',re.I),'Grainger'),
    (re.compile(r'\bMSC\b',re.I),'MSC'),
    (re.compile(r'\bUline\b',re.I),'Uline'),
    (re.compile(r'\bAMZN\b|\bAmazon\b',re.I),'Amazon'),
    (re.compile(r'\bHome\s*Depot\b|\bHD\b',re.I),'Home Depot'),
    (re.compile(r"\bLowe'?s\b|\bLowes\b",re.I),"Lowe's"),
    (re.compile(r'\bAce\s*(?:Hdwr|Hardware)?\b',re.I),'ACE Hardware'),
    (re.compile(r'\bFerguson\b|\bFerg\.?\b',re.I),'Ferguson'),
    (re.compile(r'\bAdvantage\b',re.I),'Advantage / Scott Electric'),
    (re.compile(r'\bBath\s*Fitter\b|\bBF\b',re.I),'Bath Fitter Corporate'),
    (re.compile(r'\bWingits\b',re.I),'Wingits'),
]

def clean(x):
    return re.sub(r'\s+',' ',str(x or '')).strip()

def infer_vendor(raw, default):
    txt = clean(raw)
    for pat,name in ALIASES:
        if pat.search(txt): return name
    if txt.lower().startswith('jason to order'): return 'Corporate Purchasing'
    return default

def row_restrictions(text):
    raw = clean(text)
    low=raw.lower()
    out=[]
    if 'corp transfer' in low or 'corporate transfer' in low or 'sent from corporate only' in low:
        out.append('Corporate transfer only.')
    if 'service item' in low or 'services only' in low or 'svc item' in low:
        out.append('Service item only.')
    m=re.search(r'offices?\s+([0-9,\sand]+)\s+only', raw, re.I)
    if m: out.append(f"Restricted to offices {clean(m.group(1))} only.")
    if 'pickup only' in low: out.append('Pickup only.')
    if 'order through wingits' in low: out.append('Order through Wingits.')
    if 'backup only' in low or 'back-up' in low or 'backup.' in low: out.append('Backup source/item only.')
    mm = re.search(r'(?:multiples? of|qty\'?s of|order qty\s*)(\d+)', raw, re.I)
    if mm: out.append(f"Order in multiples of {mm.group(1)}.")
    mm = re.search(r'\bOM\s*(\d+)\s*/?per', raw, re.I)
    if mm and f"Order in multiples of {mm.group(1)}." not in out:
        out.append(f"Order in multiples of {mm.group(1)}.")
    return out

def find_label_box(page, label):
    hits=page.search_for(label)
    if not hits: return None
    r=hits[0]
    if label.lower().startswith('date'):
        return [round(r.x1+4,2), round(r.y0-2,2), round(min(r.x1+110,page.rect.width-12),2), round(r.y1+6,2)]
    return [round(r.x1+5,2), round(r.y0-2,2), round(min(r.x1+85,page.rect.width-12),2), round(r.y1+6,2)]

def page_column_config(filename, page_no, table):
    if filename == '84 Lumber.pdf':
        return dict(part=2,vendor_item=0,description=1,pack=None,request_per=None,requested=3,vendor=None,header_rows=0)
    if filename == 'Sales Kit-Corp Order Only.pdf':
        return dict(part=1,vendor_item=1,description=0,pack=None,request_per=None,requested=2,vendor=3,header_rows=0)
    if filename == 'BF Walls & Accessories (1).pdf':
        return dict(part=3,vendor_item=3,description=0,pack=1,request_per=2,requested=4,vendor=None,header_rows=1)
    if filename in ('Home Depot Lumber.pdf',"Lowe's Tools and Lumber.pdf"):
        return dict(part=2,vendor_item=0,description=1,pack=None,request_per=None,requested=3,vendor=None,header_rows=1 if page_no==1 else 0)
    return dict(part=4,vendor_item=0,description=1,pack=2,request_per=3,requested=5,vendor=None,header_rows=1)

def normalize_part_candidates(part_raw, vendor_item, desc):
    raw=clean(part_raw)
    if not raw:
        raw=clean(vendor_item)
    if not raw:
        return []
    if raw.lower() in {'requested','internal item#','internal item #','item#','item #','order qty','amount'}:
        return []
    candidates=[]
    for line in re.split(r'[\n\r]+', raw):
        line=clean(line)
        if line and len(line)<=64: candidates.append(line)
    if not candidates: candidates=[raw]
    cleaned=[]
    for c in candidates:
        m=re.search(r'#\s*([A-Z0-9][A-Z0-9_.\-/]+)',c,re.I)
        cleaned.append(m.group(1) if m else c)
    out=[]
    for c in cleaned:
        c=clean(c)
        if c and c not in out: out.append(c)
    return out

catalog={'version':1,'office_number':'93','location':'Davenport','templates':[],'sources':[]}
source_index=0
for filename in FILES:
    p=ROOT/filename
    doc=fitz.open(p)
    template_id, template_name, default_vendor = FORM_META[filename]
    tentry={'template_id':template_id,'template_name':template_name,'file_name':filename,'page_count':doc.page_count,
            'default_vendor':default_vendor,'active_for_ordering': filename != 'Lumber Order Sheet Test.pdf',
            'warnings':FORM_WARNINGS.get(template_id,[]),'pages':[]}
    for pi,page in enumerate(doc, start=1):
        tentry['pages'].append({'page':pi,'date_box':find_label_box(page,'Date:'),'office_box':find_label_box(page,'Office #') or find_label_box(page,'Office')})
        tabs=page.find_tables().tables
        if not tabs: continue
        table=max(tabs,key=lambda t:t.row_count*t.col_count)
        rows=table.extract()
        cfg=page_column_config(filename,pi,table)
        for ri,row in enumerate(rows):
            if ri < cfg['header_rows']: continue
            vals=list(row)+[None]*(table.col_count-len(row))
            part_raw=vals[cfg['part']] if cfg['part'] is not None and cfg['part']<len(vals) else ''
            desc=clean(vals[cfg['description']]) if cfg['description'] is not None else ''
            vendor_item=clean(vals[cfg['vendor_item']]) if cfg['vendor_item'] is not None else ''
            pack=clean(vals[cfg['pack']]) if cfg['pack'] is not None and cfg['pack']<len(vals) else ''
            reqper=clean(vals[cfg['request_per']]) if cfg['request_per'] is not None and cfg['request_per']<len(vals) else ''
            vendor_raw=clean(vals[cfg['vendor']]) if filename=='Sales Kit-Corp Order Only.pdf' else vendor_item
            if not desc and not clean(part_raw): continue
            req_cell = table.rows[ri].cells[cfg['requested']] if cfg['requested'] is not None and cfg['requested']<len(table.rows[ri].cells) else None
            if req_cell is None: continue
            part_candidates=normalize_part_candidates(part_raw,vendor_item,desc)
            if not part_candidates: continue
            if len(part_candidates)==1 and part_candidates[0].lower() in {'tools','screws','misc.','drywall','plywood','foam and insulation','fraiming studs','moulding'}:
                continue
            all_text=' | '.join(clean(v) for v in vals if v)
            restrictions=[]
            for warning in FORM_WARNINGS.get(template_id,[]):
                if warning not in restrictions: restrictions.append(warning)
            for warning in row_restrictions(all_text):
                if warning not in restrictions: restrictions.append(warning)
            vendor=infer_vendor(vendor_raw,default_vendor)
            for part_number in part_candidates:
                source_index+=1
                catalog['sources'].append({
                    'source_key':f'{template_id}:p{pi}:r{ri}:{source_index}',
                    'template_id':template_id,
                    'template_name':template_name,
                    'file_name':filename,
                    'page':pi,
                    'row_index':ri,
                    'part_number':part_number,
                    'description':desc,
                    'vendor':vendor,
                    'vendor_item_number':vendor_item,
                    'pack_count':pack,
                    'request_per':reqper,
                    'request_box':[round(float(x),2) for x in req_cell],
                    'restrictions':restrictions,
                })
    catalog['templates'].append(tentry)

out=ROOT/'order_form_catalog.json'
out.write_text(json.dumps(catalog,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
print('templates',len(catalog['templates']),'sources',len(catalog['sources']),'bytes',out.stat().st_size)

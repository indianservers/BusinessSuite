"""Literal local slide drafting/editing; never inferred business facts."""
import re
from copy import deepcopy
from fastapi import HTTPException


def slide(text):
    parts=[p.strip() for p in text.split('|')]
    return {'title':parts[0],'bullets':parts[1:]}


def parse(text,title):
    if not text.strip():return [{'title':title,'bullets':['Add verified findings.','Agree next steps.']}]
    return [slide(part.strip()) for part in re.split(r'\s*\|\|\s*|\n\s*---\s*\n',text)]


def edit(slides,operation):
    values=deepcopy(slides)
    def index(value):
        result=int(value)-1
        if not 0<=result<len(values):raise HTTPException(422,'Select an existing slide number from the current draft')
        return result
    match=re.fullmatch(r'(?is)add (?:a )?slide\s*:\s*(.+)',operation)
    if match:values.append(slide(match[1]));return values
    match=re.fullmatch(r'(?is)replace slides\s*:\s*(.+)',operation)
    if match:return parse(match[1],'')
    match=re.fullmatch(r'(?is)replace slide (\d+)\s*:\s*(.+)',operation)
    if match:values[index(match[1])]=slide(match[2]);return values
    match=re.fullmatch(r'(?is)rename slide (\d+) to\s+(.+)',operation)
    if match:values[index(match[1])]['title']=match[2].strip();return values
    match=re.fullmatch(r'(?is)remove slide (\d+)[. ]*',operation)
    if match:
        del values[index(match[1])]
        if not values:raise HTTPException(422,'Keep at least one slide in a presentation')
        return values
    match=re.fullmatch(r'(?is)move slide (\d+) to (\d+)[. ]*',operation)
    if match:
        origin,target=index(match[1]),index(match[2]);values.insert(target,values.pop(origin));return values
    match=re.fullmatch(r'(?is)add (?:a )?point to slide (\d+)\s*:\s*(.+)',operation)
    if match:values[index(match[1])]['bullets'].append(match[2].strip());return values
    match=re.fullmatch(r'(?is)(replace|remove) point (\d+) (?:on|from) slide (\d+)(?:\s*:\s*(.+))?',operation)
    if match:
        points=values[index(match[3])]['bullets'];point=int(match[2])-1
        if not 0<=point<len(points):raise HTTPException(422,'Select an existing point number from that slide')
        if match[1].lower()=='remove' and not match[4]:del points[point]
        elif match[1].lower()=='replace' and match[4]:points[point]=match[4].strip()
        else:return None
        return values
    return None

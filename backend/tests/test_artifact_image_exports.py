import io
import hashlib
import zipfile
import pytest
from fastapi import HTTPException
from PIL import Image
from pypdf import PdfReader
from app.ai_operator import artifacts
from tests.test_artifact_images import persist
from tests.test_suite_operator import setup_suite,ROOT
from tests.test_suite_workspace import chat
from tests.test_bot_artifacts import command,execute
from tests.test_ai_operator import isolate_generic_http_audit
from tests.rich_text_test_utils import organization_context


def inputs():
    stream=io.BytesIO();Image.new('RGBA',(400,200),'blue').save(stream,format='PNG');pixels=stream.getvalue()
    image={'id':1,'kind':'image','title':'Pinned illustration','content':'Synthetic blue rectangle','module':'CRM','revision':1,
        'image':{'mime_type':'image/png','size':len(pixels),'width':400,'height':200,'sha256':hashlib.sha256(pixels).hexdigest()}}
    dashboard={'kind':'dashboard','title':'Illustrated delivery report','content':'Synthetic export verification','module':'CRM','revision':1,
        'panels':[{'artifact_id':1,'revision':1,'label':'Delivery illustration'}]}
    return dashboard,image,pixels


@pytest.mark.parametrize('fmt',['pdf','docx','xlsx'])
def test_image_dashboard_requires_exact_pixels_and_embeds_them(fmt):
    dashboard,image,pixels=inputs()
    with pytest.raises(HTTPException):artifacts.render_download(dashboard,fmt,[image])
    with pytest.raises(HTTPException):artifacts.render_download(dashboard,fmt,[image],source_media={1:b'corrupt'})
    output,mime=artifacts.render_download(dashboard,fmt,[image],source_media={1:pixels})
    if fmt=='pdf':
        reader=PdfReader(io.BytesIO(output));assert len(reader.pages)==2
        pictures=[value.image for page in reader.pages for value in page.images]
        assert len(pictures)==1 and pictures[0].size==(400,200)
    else:
        with zipfile.ZipFile(io.BytesIO(output)) as archive:
            media=[name for name in archive.namelist() if '/media/' in name]
            assert len(media)==1 and archive.read(media[0])==pixels


def test_private_image_dashboard_exports_pinned_version(client,db):
    h,user,_,_=setup_suite(client,db);ident=chat(client,h);receipt,blue=persist(db,user,ident)
    body={'title':'Private illustrated report','kind':'dashboard','content':'Pinned image',
        'panels':[{'artifact_id':receipt['artifact_id'],'revision':1}]}
    run=execute(client,db,h,command(client,h,'CRM','Prepare illustration report',local_plan={
        'summary':'Review pinned image dashboard','steps':[{'tool':'crm.create_artifact','payload':body}]}))
    dashboard=run['receipts'][0]['artifact_id'];persist(db,user,ident,'red',receipt)
    for fmt in ('pdf','docx','xlsx'):
        response=client.get(ROOT+f'/artifacts/{dashboard}/download',headers=h,params={'format':fmt})
        assert response.status_code==200
        if fmt=='pdf':
            pictures=[value.image.convert('RGBA') for page in PdfReader(io.BytesIO(response.content)).pages for value in page.images]
            assert pictures[0].getpixel((0,0))==(0,0,255,255)
        else:
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                assert any(archive.read(name)==blue for name in archive.namelist() if '/media/' in name)
    assert client.delete(ROOT+f'/artifacts/{receipt["artifact_id"]}',headers=h).status_code==200
    assert client.get(ROOT+f'/artifacts/{dashboard}/download',headers=h,params={'format':'pdf'}).status_code==404

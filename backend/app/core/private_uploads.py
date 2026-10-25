"""Keep PMS submission evidence behind its permission-checked download APIs."""
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles


class ProtectedUploads(StaticFiles):
    def get_path(self, scope):
        raw=scope.get('path','')
        if '\\' in raw or ':' in raw or raw.startswith('//'):
            raise HTTPException(404,'Not found')
        return super().get_path(scope)

    async def get_response(self, path, scope):
        # Reject Windows drive/UNC syntax before StaticFiles calls realpath.
        if path.startswith('\\\\') or ':' in path or path.startswith('//'):
            raise HTTPException(404,'Not found')
        parts=tuple(path.replace('\\','/').strip('/').lower().split('/'))
        # Only explicitly public presentation assets may use permanent URLs.
        if parts[:1] not in {('photos',),('avatars',),('logos',),('branding',)}:
            raise HTTPException(404,'Not found')
        return await super().get_response(path,scope)

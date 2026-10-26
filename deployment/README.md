# Deploy the same revision to every site

`sites.json` registers production suite and Interns Hub projects. Source code comes from one committed revision of `main`. Each project retains its existing backend environment, database and secrets. Public portal URLs and Firebase web settings remain specific to each registry entry.

## Automatic releases

Set the GitHub Actions repository secret `VERCEL_TOKEN` to a deployment token with access to the registered projects. Do not commit it. Rotate it before its expiry. On pushes to `main`, `.github/workflows/release-sites.yml` builds the portable portal once, deploys all registry entries with at most two simultaneous deployments, and checks each live `/release.json` against the commit being released. A failed deployment stays visible in its own matrix job; the other projects continue. The workflow can also be run manually. Production runs are serialized so an older run cannot replace a newer one.

The workflow deliberately fails before deployment when the token is missing. A Git push alone does not update a disconnected Vercel project without this workflow credential.

## Local releases

Install Python 3.12, Node 22+ and Vercel CLI 65.1.0. Authenticate Vercel and commit the source tree. Run from the repository root:

```powershell
python scripts/release_sites.py
npm ci --prefix frontend
npm ci --prefix frontend/interns-hub
npm run build --prefix frontend/interns-hub
python scripts/release_sites.py --deploy --portal-dist frontend/interns-hub/dist
```

Without `--deploy`, the script only prints the release plan. Use `--site indianservers-suite` to release a single registered project. Releases use a clean Git archive, never local environment files, generated data or uncommitted source. Portal artifacts must contain the same commit SHA as the source archive. Vercel builds suite frontends with the release SHA explicitly supplied.

## Add another customer site

Create its Vercel project and assign its domain. Provision backend environment variables and storage for suite projects; retain a separate database or existing tenant configuration as intended for that customer. Add a unique site ID, kind, existing project/team IDs and HTTPS origin to `sites.json`. Portal entries additionally need public API/admin URLs and the matching public Firebase web configuration. Enable the identity providers and authorize the new domains in that Firebase project. Provider client secrets remain in the provider/backend configuration.

Commit and push `main`. All registered entries receive that code revision through the release workflow once `VERCEL_TOKEN` is configured. Domain registration does not itself enroll a site. There is no hardcoded two-customer limit in the registry or release script; deployments remain subject to hosting capacity and account limits.

A shared code release does not merge customer data, credentials, branding or permission assignments. Google/Microsoft buttons are shared UI, while the provider must also be enabled in each installation's identity configuration.

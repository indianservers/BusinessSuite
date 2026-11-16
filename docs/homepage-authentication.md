# Business Suite homepage authentication

The public `/` homepage embeds the existing login and three-step trial application components. `/login`, `/signup`, recovery links, MFA challenges required by an existing account policy, SSO callbacks, and pending-approval handling remain available. This redesign does not enable or require MFA, change permissions, grant trial access, change tenant routing, or modify database schemas.

Application selection is stored in the validated `next` query parameter. Login completes through `/continue?next=...`, where existing authorization chooses the accessible destination. The inline signup/status/recovery switches retain `next`. On mobile, the home initially shows four compact application rows with Schedule & Appointments first; Show all reveals all seven. Login/signup opens in a focus-trapped, dismissible bottom panel, keeping the home short. Desktop retains the inline authentication column. A trial application still requires organization approval and does not create an authenticated session.

## Google and Microsoft configuration

Keep the installation's existing backend settings:

- `FIREBASE_PROJECT_ID`: Firebase project ID.
- `FIREBASE_WEB_CONFIG`: JSON containing `apiKey`, `authDomain`, `projectId`, and `appId` for that same project. Optional `storageBucket` and `messagingSenderId` remain supported. Do not put private service-account keys in this public web configuration.
- `FIREBASE_GOOGLE_AUTH_DOMAIN`: optional Google-specific authorized auth domain. Microsoft continues using `FIREBASE_WEB_CONFIG.authDomain`.
- `FRONTEND_PUBLIC_URL` and `BACKEND_PUBLIC_URL`: the deployment's public frontend and backend origins for existing enterprise SSO flows.

Enable Google and/or Microsoft in Firebase Authentication. Add the frontend's actual hostname to Firebase's Authorized domains. For this task's local preview the frontend origin is `http://127.0.0.1:5174`; add the origin and hostname actually used by each deployment.

For Google One Tap, set the frontend build variable `VITE_GOOGLE_ONE_TAP_CLIENT_ID` to the Google OAuth **Web application** client ID associated with the configured Firebase Google provider. Rebuild the frontend after setting it. Add the exact frontend origin (scheme, host, and port) to that client's Authorized JavaScript origins. Production must use HTTPS. Without this variable the ambient prompt is skipped and the regular provider buttons continue to work.

Google's standard Firebase callback URL is `https://<google-auth-domain>/__/auth/handler`, where `<google-auth-domain>` is `FIREBASE_GOOGLE_AUTH_DOMAIN` when provided, otherwise `FIREBASE_WEB_CONFIG.authDomain`. Register it as an authorized redirect URI for the Google OAuth web client.

For Microsoft, configure the Microsoft provider's client ID and client secret **in Firebase Authentication**, and register `https://<FIREBASE_WEB_CONFIG.authDomain>/__/auth/handler` as the Microsoft Entra application's Web redirect URI. No new Microsoft secret or frontend secret variable is introduced by this change. Existing enterprise OIDC provider entries remain supported with callback `<BACKEND_PUBLIC_URL>/api/v1/auth/sso/callback/oidc/<provider_id>`; their provider configuration and callback/state validation are unchanged.

One Tap is rendered exclusively by Google Identity Services. Automatic account selection is disabled. One prompt is attempted per browser-tab session within 24 hours; dismissal/unavailability does not trigger a loop, and the prompt is cancelled when the user starts entering credentials or switches auth views. Browser policy, account eligibility, and Google cooldown can suppress it. The Google button remains the fallback.

The GIS ID credential is exchanged with Firebase using `GoogleAuthProvider.credential` and `signInWithCredential`. The resulting Firebase token goes to the existing `/auth/firebase/login` endpoint, whose backend verifier checks signature, issuer, audience, expiry, verified email, and the allowed provider. Existing account discovery, workspace choice, organization access, approval, and MFA policy are applied there. The frontend never calls an account-link/merge API or retries account-collision errors by linking accounts.

The existing signup identity endpoint supports Google prefill. Microsoft remains a login option; Microsoft signup prefill is not offered because the current signup backend does not provide that capability. Email trial applications remain available regardless of provider configuration.

Official integration references: [Google GIS JavaScript API](https://developers.google.com/identity/gsi/web/reference/js-reference) and [Firebase Google sign-in](https://firebase.google.com/docs/auth/web/google-signin).

## Verification

Run `node scripts/test-homepage-redesign.cjs` from `frontend` for the browser regression suite and `npx tsc --noEmit` for frontend types. The browser regression uses stubbed API responses to check search/categories, all seven application destinations and Company Admin, inline signup validation and submission, pending approval/status, password recovery/reset, rejected and successful password login without an added MFA challenge, preserved destinations, unavailable-provider fallback, keyboard tab navigation, and viewport widths from 320 to 1585 pixels. GIS lifecycle is tested with an SDK test double (no identity or credential is fabricated), including disabled automatic selection, input cancellation, and suppression after reload. Mobile checks cover expansion, panel dismissal/reopening, and a default home height below 1000 pixels.

Stubbed responses do not establish live provider or email delivery success. Complete a Google/Microsoft sign-in and a One Tap credential round-trip against the configured deployment with approved test accounts before production rollout. Verify password recovery/status email delivery against that deployment's mail service as well.

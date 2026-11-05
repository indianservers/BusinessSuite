async function loadSDK() {
    const fb = () => window.FB;
    // sdk.js exposes a buffering placeholder before fbAsyncInit. Capturing it
    // makes later login() calls queue forever instead of opening a popup.
    const ready = () => fb() && !("__buffer" in fb());
    if (ready())
        return fb();
    await new Promise((resolve, reject) => {
        const host = window;
        const previous = host.fbAsyncInit;
        let script = document.getElementById("business-suite-facebook-sdk");
        const timeout = window.setTimeout(() => reject(new Error("Meta SDK could not load. Refresh and try again.")), 15000);
        const loaded = () => { if (ready()) {
            window.clearTimeout(timeout);
            resolve();
        } };
        host.fbAsyncInit = () => { try {
            previous?.();
        }
        finally {
            loaded();
        } };
        if (!script) {
            script = document.createElement("script");
            script.id = "business-suite-facebook-sdk";
            script.src = "https://connect.facebook.net/en_US/sdk.js";
            script.async = true;
            script.crossOrigin = "anonymous";
        }
        script.addEventListener("load", loaded, { once: true });
        script.addEventListener("error", () => { window.clearTimeout(timeout); reject(new Error("Meta SDK could not load")); }, { once: true });
        if (!script.isConnected)
            document.body.appendChild(script);
        loaded();
    });
    if (!fb())
        throw new Error("Meta SDK is unavailable");
    return fb();
}

const button = document.getElementById('continue');
const status = document.getElementById('status');
const workspace = document.getElementById('workspace');
let session, code, assets, sent = false, launched = false;
const ticket = location.hash.slice(1);
history.replaceState(null, '', location.pathname);
function report(message) { status.textContent = message; }
function send() {
    if (!session || !code || !assets || sent || Date.now() >= session.expires || !window.opener) return;
    sent = true;
    window.opener.postMessage({ type: 'SUITE_WHATSAPP_AUTH', state: session.state, code, ...assets }, location.origin);
    code = null;
    report('Meta authorization received. Business Suite is verifying the connection…');
}
window.addEventListener('message', event => {
    if (!session) return;
    if (event.source === window.opener && event.origin === location.origin && event.data?.type === 'SUITE_WHATSAPP_RESULT' && event.data.state === session.state) {
        report(event.data.success ? 'WhatsApp connected. You can close this window and return to Business Suite.' : 'Business Suite could not verify the connection. Return to its dashboard to review the error and start again.');
        return;
    }
    if (!launched || event.origin !== 'https://www.facebook.com') return;
    let value;
    try { value = typeof event.data === 'string' ? JSON.parse(event.data) : event.data; } catch { return; }
    if (value?.type !== 'WA_EMBEDDED_SIGNUP') return;
    if (['FINISH', 'FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING'].includes(value.event)) {
        if (!/^\d{5,40}$/.test(String(value.data?.waba_id)) || !/^\d{5,40}$/.test(String(value.data?.phone_number_id))) {
            report('Meta did not return the account and phone identifiers. Return to Business Suite and start again.'); return;
        }
        assets = { wabaId: String(value.data.waba_id), phoneNumberId: String(value.data.phone_number_id) }; send();
    } else if (['CANCEL', 'ERROR'].includes(value.event) && !sent) {
        report('Meta signup did not finish. Return to Business Suite and start a new connection.');
    }
});
async function prepare() {
    if (!ticket || !window.opener) return;
    try {
        session = JSON.parse(decodeURIComponent(ticket));
        if (!/^[A-Za-z0-9_-]{43}$/.test(session.state) || !/^\d+$/.test(session.appId) || !/^\d+$/.test(session.configId) || !/^v\d+\.\d+$/.test(session.apiVersion) || !(session.expires > Date.now() && session.expires - Date.now() <= 600000)) throw new Error('Signup link expired or is invalid. Start again in Business Suite.');
        workspace.textContent = 'Business Suite: ' + location.origin;
        await loadSDK();
        window.FB.init({ appId: session.appId, version: session.apiVersion, cookie: true, xfbml: false, fedCM: false });
        button.hidden = false; button.disabled = false;
        report('Ready. Continue to Meta to authorize your business account.');
        setTimeout(() => { if (!sent) { button.disabled = true; session = null; code = null; assets = null; report('This signup link expired. Start again from Business Suite.'); } }, Math.max(0, session.expires - Date.now()));
    } catch (error) { session = null; report(error.message); }
}
button.addEventListener('click', () => {
    if (!session || launched || Date.now() >= session.expires) return;
    launched = true; button.disabled = true;
    report('Complete the Meta popup, then return here.');
    try {
        window.FB.login(response => {
            if (sent || !session) return;
            if (response.authResponse?.code) { code = response.authResponse.code; send(); }
            else report('Meta did not return an authorization code. Start again from Business Suite.');
        }, { config_id: session.configId, response_type: 'code', override_default_response_type: true, extras: { version: 'v4' } });
    } catch { report('Meta could not open. Allow popups and start again from Business Suite.'); }
});
void prepare();

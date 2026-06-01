const GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com";

let _idToken = null;
let _tokenExpiry = 0;
const _tokenWaiters = [];

function _onGoogleCredential(response) {
    try {
        const payload = JSON.parse(atob(response.credential.split('.')[1]));
        _tokenExpiry = payload.exp * 1000;
    } catch {
        _tokenExpiry = Date.now() + 3_600_000;
    }
    _idToken = response.credential;
    _tokenWaiters.splice(0).forEach(fn => fn(_idToken));
}

// Called by the GSI library once it has loaded.
window.onGoogleLibraryLoad = function () {
    google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: _onGoogleCredential,
        auto_select: true,
        use_fedcm_for_prompt: true,
    });
    google.accounts.id.prompt();
};

export function clearTokenCache() {
    _idToken = null;
    _tokenExpiry = 0;
}

/**
 * Returns Promise<string|null>.
 * Resolves with cached token if still valid; otherwise waits up to 5s for GSI.
 */
export function getIdToken() {
    if (_idToken && Date.now() < _tokenExpiry - 60_000) {
        return Promise.resolve(_idToken);
    }
    if (typeof google !== "undefined" && google.accounts?.id) {
        google.accounts.id.prompt();
    }
    return new Promise(resolve => {
        let settled = false;
        const timer = setTimeout(() => {
            if (!settled) { settled = true; resolve(null); }
        }, 5_000);
        _tokenWaiters.push(token => {
            if (!settled) { settled = true; clearTimeout(timer); resolve(token); }
        });
    });
}

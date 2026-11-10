import { getApps, initializeApp, type FirebaseOptions } from "firebase/app";
import { getAuth, GoogleAuthProvider, OAuthProvider, inMemoryPersistence, setPersistence, signInWithPopup, signInWithRedirect, getRedirectResult, signOut } from "firebase/auth";
import { api, authApi } from "./api";

export const SOCIAL_REDIRECT_KEY = "suite-social-redirect-provider";
type SocialFirebaseOptions = FirebaseOptions & { googleAuthDomain?: string };

function socialAuth(config: SocialFirebaseOptions, provider: "google" | "microsoft") {
  const options = provider === "google" && config.googleAuthDomain
    ? { ...config, authDomain: config.googleAuthDomain } : config;
  // Provider-specific auth domains must not reuse an app configured for a
  // different callback. Microsoft keeps its original Firebase callback.
  const name = `suite-social-login-${options.authDomain || "default"}`;
  return getAuth(getApps().find(app => app.name === name) || initializeApp(options, name));
}

export async function startGoogleRedirect(config: SocialFirebaseOptions) {
  const auth = socialAuth(config, "google");
  await setPersistence(auth, inMemoryPersistence);
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });
  sessionStorage.setItem(SOCIAL_REDIRECT_KEY, "google");
  try {
    await signInWithRedirect(auth, provider);
  } catch (error) {
    sessionStorage.removeItem(SOCIAL_REDIRECT_KEY);
    sessionStorage.removeItem("suite-social-redirect-remember");
    throw error;
  }
}

export async function completeGoogleRedirect(config: SocialFirebaseOptions) {
  const auth = socialAuth(config, "google");
  try {
    const result = await getRedirectResult(auth);
    if (!result) throw new Error("Google did not return a sign-in result. Check that browser storage is available and try again.");
    const token=await result.user.getIdToken();
    const response=await authApi.firebaseLogin(token, undefined, "google");
    if(response.data.workspace_required)response.data={...response.data,identity_token:token,identity_provider:"google"};
    return response;
  } finally {
    sessionStorage.removeItem(SOCIAL_REDIRECT_KEY);
    sessionStorage.removeItem("suite-social-redirect-remember");
    await signOut(auth);
  }
}

export async function socialFirebaseLogin(config: SocialFirebaseOptions, module: "hrms" | "crm" | "project_management" | "srm" | "fam" | undefined, identityProvider: "google" | "microsoft" = "google") {
  const auth = socialAuth(config, identityProvider);
  await setPersistence(auth,inMemoryPersistence);
  const provider = identityProvider === "google" ? new GoogleAuthProvider() : new OAuthProvider("microsoft.com");
  provider.setCustomParameters({prompt:"select_account"});
  try {
    const result = await signInWithPopup(auth,provider);
    const token=await result.user.getIdToken();
    const response=await authApi.firebaseLogin(token, module, identityProvider);
    if(response.data.workspace_required)response.data={...response.data,identity_token:token,identity_provider:identityProvider};
    return response;
  } finally {
    await signOut(auth);
  }
}

export async function verifySignupGoogle(){
  const {data}=await authApi.firebaseConfig();
  const auth=socialAuth(data.firebase_config,"google");
  await setPersistence(auth,inMemoryPersistence);
  const provider=new GoogleAuthProvider();provider.setCustomParameters({prompt:"select_account"});
  try{
    const result=await signInWithPopup(auth,provider);
    return (await api.post("/auth/signup/identity",{token:await result.user.getIdToken()})).data;
  }finally{await signOut(auth)}
}

export async function socialStepUp(identityProvider: "google" | "microsoft") {
  const { data } = await authApi.firebaseConfig();
  const auth = socialAuth(data.firebase_config, identityProvider);
  await setPersistence(auth, inMemoryPersistence);
  const provider = identityProvider === "google" ? new GoogleAuthProvider() : new OAuthProvider("microsoft.com");
  provider.setCustomParameters({ prompt: identityProvider === "google" ? "select_account" : "login", max_age: "0" });
  try {
    const result = await signInWithPopup(auth, provider);
    return await result.user.getIdToken(true);
  } finally {
    await signOut(auth);
  }
}

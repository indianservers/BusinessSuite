import { getApps, initializeApp, type FirebaseOptions } from "firebase/app";
import { getAuth, GoogleAuthProvider, OAuthProvider, inMemoryPersistence, setPersistence, signInWithPopup, signInWithRedirect, getRedirectResult, signOut } from "firebase/auth";
import { authApi } from "./api";

export const SOCIAL_REDIRECT_KEY = "suite-social-redirect-provider";

export async function startGoogleRedirect(config: FirebaseOptions) {
  const app = getApps().find(item => item.name === "suite-social-login") || initializeApp(config, "suite-social-login");
  const auth = getAuth(app);
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

export async function completeGoogleRedirect(config: FirebaseOptions) {
  const app = getApps().find(item => item.name === "suite-social-login") || initializeApp(config, "suite-social-login");
  const auth = getAuth(app);
  try {
    const result = await getRedirectResult(auth);
    if (!result) throw new Error("Google did not return a sign-in result. Check that browser storage is available and try again.");
    return await authApi.firebaseLogin(await result.user.getIdToken(), undefined, "google");
  } finally {
    sessionStorage.removeItem(SOCIAL_REDIRECT_KEY);
    sessionStorage.removeItem("suite-social-redirect-remember");
    await signOut(auth);
  }
}

export async function socialFirebaseLogin(config: FirebaseOptions, module: "hrms" | "crm" | "project_management" | "srm" | "fam" | undefined, identityProvider: "google" | "microsoft" = "google") {
  const app = getApps().find(item=>item.name === "suite-social-login") || initializeApp(config,"suite-social-login");
  const auth = getAuth(app);
  await setPersistence(auth,inMemoryPersistence);
  const provider = identityProvider === "google" ? new GoogleAuthProvider() : new OAuthProvider("microsoft.com");
  provider.setCustomParameters({prompt:"select_account"});
  try {
    const result = await signInWithPopup(auth,provider);
    return await authApi.firebaseLogin(await result.user.getIdToken(), module, identityProvider);
  } finally {
    await signOut(auth);
  }
}

export async function socialStepUp(identityProvider: "google" | "microsoft") {
  const { data } = await authApi.firebaseConfig();
  const app = getApps().find(item => item.name === "suite-social-login") || initializeApp(data.firebase_config, "suite-social-login");
  const auth = getAuth(app);
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

import { getApps, initializeApp, type FirebaseOptions } from "firebase/app";
import { getAuth, GoogleAuthProvider, OAuthProvider, inMemoryPersistence, setPersistence, signInWithPopup, signOut } from "firebase/auth";
import { authApi } from "./api";

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

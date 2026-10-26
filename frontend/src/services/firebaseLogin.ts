import { getApps, initializeApp, type FirebaseOptions } from "firebase/app";
import { getAuth, GoogleAuthProvider, inMemoryPersistence, setPersistence, signInWithPopup, signOut } from "firebase/auth";
import { authApi } from "./api";

export async function googleFirebaseLogin(config: FirebaseOptions) {
  const app = getApps().find(item=>item.name === "suite-google-login") || initializeApp(config,"suite-google-login");
  const auth = getAuth(app);
  await setPersistence(auth,inMemoryPersistence);
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({prompt:"select_account"});
  try {
    const result = await signInWithPopup(auth,provider);
    return await authApi.firebaseLogin(await result.user.getIdToken());
  } finally {
    await signOut(auth);
  }
}

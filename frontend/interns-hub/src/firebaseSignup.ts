import { getApps, initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, setPersistence, inMemoryPersistence, signInWithPopup, signOut } from "firebase/auth";
import { firebaseConfig } from "./config";
import { hub, send } from "./api";

export async function firebaseSignup() {
  if (!firebaseConfig?.projectId) throw new Error("Social signup is not available yet. Please apply with email.");
  const app = getApps().find(item=>item.name === "intern-hub-signup") || initializeApp(firebaseConfig,"intern-hub-signup");
  const auth = getAuth(app);
  await setPersistence(auth,inMemoryPersistence);
  const identityProvider = new GoogleAuthProvider();
  identityProvider.setCustomParameters({prompt:"select_account"});
  try {
    const result = await signInWithPopup(auth,identityProvider);
    const idToken = await result.user.getIdToken();
    return await hub("/signup/firebase",send("POST",{token:idToken}));
  } finally {
    await signOut(auth);
  }
}

import { initializeApp, getApps } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  sendPasswordResetEmail,
  sendEmailVerification,
  updateProfile,
  onAuthStateChanged,
  reload as fbReload,
  signOut as fbSignOut,
} from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID,
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.REACT_APP_FIREBASE_APP_ID,
};

export const firebaseApp = getApps()[0] || initializeApp(firebaseConfig);
export const auth = getAuth(firebaseApp);

const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: "select_account" });

/**
 * Return the Firebase ID token for the currently signed-in user.
 * Force-refreshes when needed so the backend never sees a stale token.
 */
export async function getIdToken(forceRefresh = false) {
  const u = auth.currentUser;
  if (!u) return null;
  return u.getIdToken(forceRefresh);
}

export async function signInWithGoogle() {
  const cred = await signInWithPopup(auth, googleProvider);
  return { user: cred.user, idToken: await cred.user.getIdToken() };
}

export async function signUpWithEmail(email, password, displayName) {
  const cred = await createUserWithEmailAndPassword(auth, email, password);
  if (displayName) {
    try { await updateProfile(cred.user, { displayName }); } catch (_) { /* non-fatal */ }
  }
  // Trigger the Firebase verification email immediately — the caller
  // then routes to the "please verify" screen and MUST NOT create the
  // RIYORA membership until reloadFirebaseUser() reports emailVerified.
  try {
    await sendEmailVerification(cred.user);
  } catch (_) { /* non-fatal — user can hit "Resend" */ }
  return { user: cred.user, idToken: await cred.user.getIdToken() };
}

export async function resendVerificationEmail() {
  if (!auth.currentUser) throw new Error("Not signed in");
  await sendEmailVerification(auth.currentUser);
}

/**
 * Force-refresh the local Firebase user record from Firebase's servers so
 * `emailVerified` reflects a link the user just clicked in another tab.
 * Returns the refreshed ID token (already-verified) or the existing token
 * with a fresh copy of the emailVerified flag.
 */
export async function reloadFirebaseUser() {
  if (!auth.currentUser) return { user: null, idToken: null, emailVerified: false };
  await fbReload(auth.currentUser);
  // Force refresh so the JWT itself carries email_verified=true
  const idToken = await auth.currentUser.getIdToken(true);
  return {
    user: auth.currentUser,
    idToken,
    emailVerified: !!auth.currentUser.emailVerified,
  };
}

export async function signInWithEmail(email, password) {
  const cred = await signInWithEmailAndPassword(auth, email, password);
  return { user: cred.user, idToken: await cred.user.getIdToken() };
}

export async function sendResetEmail(email) {
  return sendPasswordResetEmail(auth, email);
}

export async function signOut() {
  try {
    await fbSignOut(auth);
  } catch (_) {
    /* swallow */
  }
}

export { onAuthStateChanged };

/**
 * Human-friendly error message from a Firebase auth error object.
 */
export function humanFirebaseError(err) {
  const code = (err && err.code) || "";
  const map = {
    "auth/email-already-in-use": "This email is already registered. Sign in instead.",
    "auth/invalid-email": "Please enter a valid email address.",
    "auth/weak-password": "Password must be at least 6 characters.",
    "auth/user-not-found": "No account found for this email.",
    "auth/wrong-password": "Incorrect password. Try again or reset it.",
    "auth/invalid-credential": "Incorrect email or password.",
    "auth/too-many-requests": "Too many attempts. Please try again in a few minutes.",
    "auth/popup-closed-by-user": "Google sign-in was cancelled.",
    "auth/popup-blocked": "Popup blocked by browser. Please allow popups and try again.",
    "auth/network-request-failed": "Network error. Check your connection.",
    "auth/account-exists-with-different-credential": "This email is linked to a different sign-in method.",
    "auth/unauthorized-domain":
      "This domain is not authorised for Google sign-in. If you are the admin, add this domain in Firebase Console → Authentication → Settings → Authorized domains.",
  };
  return map[code] || err?.message || "Authentication error. Please try again.";
}

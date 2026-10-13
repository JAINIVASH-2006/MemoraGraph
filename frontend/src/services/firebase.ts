import { initializeApp, getApps, type FirebaseApp } from 'firebase/app';
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut,
  updateProfile,
  type Auth,
  type UserCredential,
} from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

// Initialize Firebase App singleton
let app: FirebaseApp;
if (!getApps().length) {
  app = initializeApp(firebaseConfig);
} else {
  app = getApps()[0];
}

export let auth: Auth;
export let googleProvider: GoogleAuthProvider;

export const isFirebaseConfigured = (): boolean => {
  return Boolean(import.meta.env.VITE_FIREBASE_API_KEY);
};

try {
  if (isFirebaseConfigured()) {
    auth = getAuth(app);
    googleProvider = new GoogleAuthProvider();
  } else {
    console.warn("Firebase config missing. Authentication will fallback to local JWT.");
  }
} catch (error) {
  console.warn("Firebase Auth could not be initialized:", error);
}

export const signInWithFirebaseEmail = async (email: string, password: string): Promise<UserCredential> => {
  if (!auth) throw new Error("Firebase Auth is not initialized (missing config).");
  return await signInWithEmailAndPassword(auth, email, password);
};

export const registerWithFirebaseEmail = async (
  email: string,
  password: string,
  displayName?: string
): Promise<UserCredential> => {
  if (!auth) throw new Error("Firebase Auth is not initialized (missing config).");
  const cred = await createUserWithEmailAndPassword(auth, email, password);
  if (displayName && cred.user) {
    await updateProfile(cred.user, { displayName });
  }
  return cred;
};

export const signInWithGoogle = async (): Promise<UserCredential> => {
  if (!auth || !googleProvider) throw new Error("Firebase Auth is not configured. Google Sign-In is unavailable.");
  return await signInWithPopup(auth, googleProvider);
};

export const firebaseLogout = async (): Promise<void> => {
  if (!auth) return;
  await signOut(auth);
};

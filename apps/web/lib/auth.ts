"use client";

/**
 * Firebase authentication, kept deliberately thin.
 *
 * The browser holds an ID token and nothing else. It never sees a service
 * credential, a bucket name, or a storage path — those exist only on the
 * server, and the browser reaches storage through short-lived URLs the API
 * issues for one object at a time.
 */

import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import {
  createUserWithEmailAndPassword,
  getAuth,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut as fbSignOut,
  type Auth,
  type User,
} from "firebase/auth";

const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
};

export const authConfigured = Boolean(config.apiKey && config.authDomain);

function app(): FirebaseApp {
  return getApps().length ? getApps()[0]! : initializeApp(config);
}

export function auth(): Auth {
  return getAuth(app());
}

export async function getIdToken(): Promise<string | null> {
  if (!authConfigured) return null;
  const user = auth().currentUser;
  if (user) return user.getIdToken();

  // A page can render before Firebase has restored the session from storage.
  // Waiting once here avoids a spurious signed-out flash on first paint.
  return new Promise((resolve) => {
    const stop = onAuthStateChanged(auth(), async (u) => {
      stop();
      resolve(u ? await u.getIdToken() : null);
    });
  });
}

export function watchUser(cb: (user: User | null) => void): () => void {
  if (!authConfigured) {
    cb(null);
    return () => {};
  }
  return onAuthStateChanged(auth(), cb);
}

export const signIn = (email: string, password: string) =>
  signInWithEmailAndPassword(auth(), email, password);

export const signUp = (email: string, password: string) =>
  createUserWithEmailAndPassword(auth(), email, password);

export const signOut = () => fbSignOut(auth());

/** Firebase error codes are not sentences. Turn them into ones. */
export function readableAuthError(error: unknown): string {
  const code = (error as { code?: string })?.code ?? "";
  switch (code) {
    case "auth/invalid-credential":
    case "auth/wrong-password":
    case "auth/user-not-found":
      return "That email and password do not match an account.";
    case "auth/email-already-in-use":
      return "There is already an account with that email. Try signing in.";
    case "auth/weak-password":
      return "Use a password of at least six characters.";
    case "auth/invalid-email":
      return "That does not look like an email address.";
    case "auth/network-request-failed":
      return "Could not reach the sign-in service. Check your connection.";
    default:
      return "Sign-in failed. Please try again.";
  }
}

const SESSION_KEY = "factureflow.session"

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const apiUrl = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "")
export const isConfigured = Boolean(supabaseUrl && supabaseAnonKey)

export function savedSession() {
  try {
    const value = localStorage.getItem(SESSION_KEY)
    return value ? JSON.parse(value) : null
  } catch {
    return null
  }
}

function saveSession(session) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session))
  return session
}

async function authRequest(path, options = {}) {
  const response = await fetch(`${supabaseUrl}/auth/v1/${path}`, {
    ...options,
    headers: {
      apikey: supabaseAnonKey,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.msg || data.message || "Erreur d'authentification")
  return data
}

export async function signIn(email, password) {
  const data = await authRequest("token?grant_type=password", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })
  return saveSession(data)
}

export async function signUp(email, password) {
  const data = await authRequest("signup", {
    method: "POST",
    body: JSON.stringify({ email, password, options: { emailRedirectTo: window.location.origin } }),
  })
  return data.access_token ? saveSession(data) : data
}

export async function requestPasswordReset(email) {
  return authRequest("recover", {
    method: "POST",
    body: JSON.stringify({ email, options: { redirectTo: window.location.origin } }),
  })
}

export async function updatePassword(accessToken, password) {
  const response = await fetch(`${supabaseUrl}/auth/v1/user`, {
    method: "PUT",
    headers: { apikey: supabaseAnonKey, Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.msg || data.message || "Impossible de modifier le mot de passe")
  return data
}

export async function apiFetch(path, options = {}) {
  const session = savedSession()
  if (!session?.access_token) throw new Error("Session expirée. Reconnecte-toi.")
  const response = await fetch(`${apiUrl}${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${session.access_token}`, ...(options.headers || {}) },
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Erreur serveur (${response.status})`)
  }
  return response
}

export function signOut() {
  localStorage.removeItem(SESSION_KEY)
}

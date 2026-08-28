import { useEffect, useState } from "react"
import { isConfigured, requestPasswordReset, signIn, signUp, updatePassword } from "./auth.js"

export default function AuthGate({ onSession }) {
  const [mode, setMode] = useState("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [status, setStatus] = useState("")
  const [busy, setBusy] = useState(false)
  const [recoveryToken, setRecoveryToken] = useState("")

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1))
    if (params.get("type") === "recovery" && params.get("access_token")) setRecoveryToken(params.get("access_token"))
  }, [])

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setStatus("")
    try {
      if (mode === "recover") {
        await requestPasswordReset(email)
        setStatus("Courriel envoyé. Ouvre le lien reçu pour choisir un nouveau mot de passe.")
        return
      }
      if (recoveryToken) {
        await updatePassword(recoveryToken, password)
        window.history.replaceState({}, "", window.location.pathname)
        setRecoveryToken("")
        setMode("login")
        setStatus("Mot de passe modifié. Connecte-toi avec ton nouveau mot de passe.")
        return
      }
      const result = mode === "login" ? await signIn(email, password) : await signUp(email, password)
      if (result?.access_token) onSession(result)
      else setStatus("Compte créé. Vérifie ton courriel, puis reconnecte-toi.")
    } catch (error) {
      setStatus(error.message)
    } finally {
      setBusy(false)
    }
  }

  if (!isConfigured) {
    return <main className="auth-shell"><section className="auth-card"><h1>FACTURE<span>FLOW</span></h1><p>Configuration requise.</p><small>Ajoute VITE_SUPABASE_URL et VITE_SUPABASE_ANON_KEY dans le fichier <code>.env</code> du dashboard.</small></section></main>
  }

  const isRecovery = Boolean(recoveryToken)
  return <main className="auth-shell"><section className="auth-card">
    <h1>FACTURE<span>FLOW</span></h1>
    <p>{isRecovery ? "Choisis un nouveau mot de passe sécurisé." : mode === "login" ? "Connecte-toi à ton espace factures." : mode === "recover" ? "Entre ton courriel pour recevoir un lien sécurisé." : "Crée ton espace sécurisé gratuitement."}</p>
    <form onSubmit={submit}>
      {!isRecovery && <label>Courriel<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" /></label>}
      {mode !== "recover" && <label>Mot de passe<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength="8" required autoComplete={mode === "login" ? "current-password" : "new-password"} /></label>}
      <button disabled={busy}>{busy ? "Un instant..." : isRecovery ? "Enregistrer mon mot de passe" : mode === "recover" ? "Envoyer le lien" : mode === "login" ? "Se connecter" : "Créer mon compte"}</button>
    </form>
    {status && <p className="auth-status">{status}</p>}
    {!isRecovery && <div className="auth-links"><button className="auth-link" onClick={() => setMode(mode === "login" ? "signup" : "login")}>{mode === "login" ? "Nouveau? Créer un compte" : "Déjà un compte? Se connecter"}</button>{mode === "login" && <button className="auth-link" onClick={() => setMode("recover")}>Mot de passe oublié ?</button>}</div>}
  </section></main>
}

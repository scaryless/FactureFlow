import React from "react"
import ReactDOM from "react-dom/client"
import { useState } from "react"
import App from "./App.jsx"
import AuthGate from "./AuthGate.jsx"
import Landing from "./Landing.jsx"
import { savedSession, signOut } from "./auth.js"
import "./index.css"

function Root() {
  const [session, setSession] = useState(savedSession)
  const shouldShowApp = new URLSearchParams(window.location.search).get("app") === "1"
  if (!session && !shouldShowApp) return <Landing />
  if (!session) return <AuthGate onSession={setSession} />
  return <App session={session} onSignOut={() => { signOut(); setSession(null) }} />
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
)

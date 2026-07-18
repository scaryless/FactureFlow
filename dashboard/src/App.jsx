import { useEffect, useMemo, useRef, useState } from "react"

const API = "http://127.0.0.1:8000"

const COULEURS = {
  epicerie: "#22d3ee",
  restaurant: "#f472b6",
  abonnement: "#c084fc",
  telecom: "#a78bfa",
  energie: "#fbbf24",
  essence: "#fb7185",
  transport: "#4ade80",
  sante: "#2dd4bf",
  assurance: "#818cf8",
  credit: "#60a5fa",
  maison: "#fb923c",
  autre: "#94a3b8",
}

const CATEGORIES = Object.keys(COULEURS)

const fmt = (n) =>
  (n ?? 0).toLocaleString("fr-CA", { style: "currency", currency: "CAD" })

/* ---------- fond de particules (inspiré du dashboard futuriste) ---------- */
function Particules() {
  const ref = useRef(null)

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas.getContext("2d")
    let anim

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener("resize", resize)

    const points = Array.from({ length: 70 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 2 + 0.5,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      teinte: Math.random() > 0.5 ? "34, 211, 238" : "167, 139, 250",
      alpha: Math.random() * 0.5 + 0.15,
    }))

    const boucle = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      for (const p of points) {
        p.x = (p.x + p.vx + canvas.width) % canvas.width
        p.y = (p.y + p.vy + canvas.height) % canvas.height
        ctx.fillStyle = `rgba(${p.teinte}, ${p.alpha})`
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fill()
      }
      anim = requestAnimationFrame(boucle)
    }
    boucle()

    return () => {
      cancelAnimationFrame(anim)
      window.removeEventListener("resize", resize)
    }
  }, [])

  return <canvas className="particles" ref={ref} />
}

/* ---------- beignet des catégories, dessiné en SVG pur ---------- */
function Donut({ parCategorie, total }) {
  const rayon = 62
  const circonference = 2 * Math.PI * rayon
  let decalage = 0

  const segments = Object.entries(parCategorie).map(([cat, montant]) => {
    const fraction = total > 0 ? montant / total : 0
    const seg = {
      cat,
      montant,
      couleur: COULEURS[cat] || COULEURS.autre,
      dash: `${fraction * circonference} ${circonference}`,
      offset: -decalage * circonference,
    }
    decalage += fraction
    return seg
  })

  return (
    <div className="donut-wrap">
      <svg width="170" height="170" viewBox="0 0 170 170">
        <circle cx="85" cy="85" r={rayon} fill="none"
          stroke="rgba(148,163,184,0.1)" strokeWidth="16" />
        {segments.map((s) => (
          <circle key={s.cat} cx="85" cy="85" r={rayon} fill="none"
            stroke={s.couleur} strokeWidth="16" strokeLinecap="butt"
            strokeDasharray={s.dash} strokeDashoffset={s.offset}
            transform="rotate(-90 85 85)"
            style={{ filter: `drop-shadow(0 0 6px ${s.couleur})`, transition: "stroke-dasharray 0.8s" }} />
        ))}
        <text x="85" y="80" textAnchor="middle" fill="#e2e8f0"
          fontSize="15" fontFamily="monospace" fontWeight="bold">
          {fmt(total)}
        </text>
        <text x="85" y="98" textAnchor="middle" fill="#64748b" fontSize="9"
          fontFamily="monospace" letterSpacing="2">TOTAL</text>
      </svg>
      <div className="legende">
        {segments.map((s) => (
          <div className="legende-item" key={s.cat}>
            <span className="pastille" style={{ background: s.couleur, color: s.couleur }} />
            <span>{s.cat}</span>
            <span style={{ color: "#64748b", fontFamily: "monospace" }}>{fmt(s.montant)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ---------- barres mensuelles en pur CSS ---------- */
function BarresMensuelles({ parMois }) {
  const max = Math.max(...Object.values(parMois), 1)
  return (
    <div className="bars">
      {Object.entries(parMois).map(([mois, montant]) => (
        <div className="bar-col" key={mois}>
          <span className="bar-montant">{montant > 0 ? fmt(montant) : ""}</span>
          <div className="bar" style={{ height: `${(montant / max) * 100}%` }} />
          <span className="bar-label">{mois}</span>
        </div>
      ))}
    </div>
  )
}

/* ---------- application ---------- */
export default function App() {
  const [factures, setFactures] = useState([])
  const [heure, setHeure] = useState(new Date())
  const [toast, setToast] = useState(null)
  const [glisse, setGlisse] = useState(false)
  const [chargement, setChargement] = useState(false)
  const [tri, setTri] = useState({ cle: "created_at", dir: -1 })
  const [filtreCat, setFiltreCat] = useState("toutes")
  const [filtreStatut, setFiltreStatut] = useState("tous")
  const [filtrePortee, setFiltrePortee] = useState("toutes")
  const [portee, setPortee] = useState("personnel")

  const notifier = (msg) => {
    setToast(msg)
    setTimeout(() => setToast(null), 4000)
  }

  const charger = async () => {
    try {
      const r = await fetch(`${API}/invoices`)
      setFactures(await r.json())
    } catch {
      notifier("⚠️ API injoignable — lance uvicorn dans api/")
    }
  }

  useEffect(() => { charger() }, [])
  useEffect(() => {
    const t = setInterval(() => setHeure(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  /* ----- calculs dérivés ----- */
  const stats = useMemo(() => {
    const parCategorie = {}
    const parMois = {}
    let total = 0, taxes = 0, taxesEntreprise = 0, aValider = 0

    const maintenant = new Date()
    for (let i = 5; i >= 0; i--) {
      const d = new Date(maintenant.getFullYear(), maintenant.getMonth() - i, 1)
      parMois[d.toLocaleDateString("fr-CA", { month: "short" })] = 0
    }

    for (const f of factures) {
      total += f.total || 0
      taxes += (f.tps || 0) + (f.tvq || 0)
      if (f.portee === "entreprise") taxesEntreprise += (f.tps || 0) + (f.tvq || 0)
      if (f.statut !== "ok") aValider++
      const cat = f.categorie || "autre"
      parCategorie[cat] = (parCategorie[cat] || 0) + (f.total || 0)

      const d = new Date(f.date || f.created_at)
      const cle = d.toLocaleDateString("fr-CA", { month: "short" })
      if (cle in parMois) parMois[cle] += f.total || 0
    }

    const echeances = factures
      .filter((f) => f.date_echeance && new Date(f.date_echeance) >= maintenant)
      .sort((a, b) => new Date(a.date_echeance) - new Date(b.date_echeance))
      .slice(0, 5)

    return { parCategorie, parMois, total, taxes, taxesEntreprise, aValider, echeances }
  }, [factures])

  /* ----- tri et filtres du tableau ----- */
  const facturesAffichees = useMemo(() => {
    let liste = [...factures]
    if (filtreCat !== "toutes")
      liste = liste.filter((f) => (f.categorie || "autre") === filtreCat)
    if (filtreStatut !== "tous")
      liste = liste.filter((f) => f.statut === filtreStatut)
    if (filtrePortee !== "toutes")
      liste = liste.filter((f) => (f.portee || "personnel") === filtrePortee)
    liste.sort((a, b) => {
      const va = a[tri.cle], vb = b[tri.cle]
      if (va == null) return 1
      if (vb == null) return -1
      return (va > vb ? 1 : va < vb ? -1 : 0) * tri.dir
    })
    return liste
  }, [factures, tri, filtreCat, filtreStatut, filtrePortee])

  const trierPar = (cle) =>
    setTri((t) => (t.cle === cle ? { cle, dir: -t.dir } : { cle, dir: 1 }))
  const fleche = (cle) =>
    tri.cle === cle ? (tri.dir === 1 ? " ↑" : " ↓") : ""

  /* ----- actions ----- */
  const televerser = async (fichier) => {
    if (!fichier) return
    setChargement(true)
    notifier(`⏳ Analyse de ${fichier.name}...`)
    const corps = new FormData()
    corps.append("file", fichier)
    corps.append("portee", portee)
    try {
      const r = await fetch(`${API}/extract`, { method: "POST", body: corps })
      const data = await r.json()
      if (data.verdict === "doublon") notifier("♻️ Fichier déjà traité — ignoré.")
      else if (data.verdict === "ok") notifier(`✅ ${data.donnees?.fournisseur ?? "Facture"} — ${fmt(data.donnees?.total)}`)
      else notifier(`⚠️ Facture ajoutée, à vérifier : ${(data.avertissements || []).join("; ")}`)
      await charger()
    } catch {
      notifier("❌ Erreur pendant l'extraction.")
    }
    setChargement(false)
  }

  const valider = async (id) => {
    await fetch(`${API}/invoices/${id}/valider`, { method: "POST" })
    notifier("✅ Facture validée.")
    charger()
  }

  const changerPortee = async (id, nouvellePortee) => {
    await fetch(`${API}/invoices/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ portee: nouvellePortee }),
    })
    notifier(`💼 Dépense marquée : ${nouvellePortee}`)
    charger()
  }

  const changerCategorie = async (id, categorie) => {
    await fetch(`${API}/invoices/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ categorie }),
    })
    notifier(`🏷️ Catégorie mise à jour : ${categorie}`)
    charger()
  }

  const supprimer = async (id) => {
    const f = factures.find((x) => x.id === id)
    const detail = f ? `${f.fournisseur ?? "Inconnu"} — ${fmt(f.total)}` : "cette facture"
    if (!window.confirm(`Supprimer définitivement ${detail} ?\nCette action est irréversible.`)) {
      return
    }
    await fetch(`${API}/invoices/${id}`, { method: "DELETE" })
    notifier("🗑️ Facture supprimée.")
    charger()
  }

  const joursAvant = (dateStr) => {
    const diff = Math.ceil((new Date(dateStr) - new Date()) / 86400000)
    return diff <= 0 ? "aujourd'hui" : `${diff} j`
  }

  return (
    <>
      <Particules />
      <div className="app">
        <header className="topbar">
          <div className="logo">
            <div className="logo-orb" />
            <span>FACTURE<em>FLOW</em></span>
          </div>
          <div className="clock">
            <strong>{heure.toLocaleTimeString("fr-CA")}</strong>
            {heure.toLocaleDateString("fr-CA", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
          </div>
        </header>

        {/* ----- KPI ----- */}
        <div className="grid grid-kpi">
          <div className="card">
            <h3>Dépenses totales</h3>
            <div className="kpi-value">{fmt(stats.total)}</div>
            <div className="kpi-sub">{factures.length} document{factures.length > 1 ? "s" : ""}</div>
          </div>
          <div className="card">
            <h3>Taxes récupérables (entreprise)</h3>
            <div className="kpi-value">{fmt(stats.taxesEntreprise)}</div>
            <div className="kpi-sub">{fmt(stats.taxes)} de TPS+TVQ au total</div>
          </div>
          <div className={"card" + (stats.aValider > 0 ? " kpi-alert" : "")}>
            <h3>À vérifier</h3>
            <div className="kpi-value">{stats.aValider}</div>
            <div className="kpi-sub">{stats.aValider > 0 ? "action requise ci-dessous" : "tout est validé ✓"}</div>
          </div>
          <div className="card">
            <h3>Catégorie dominante</h3>
            <div className="kpi-value" style={{ fontSize: "1.4rem" }}>
              {Object.entries(stats.parCategorie).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—"}
            </div>
            <div className="kpi-sub">sur les 6 derniers mois</div>
          </div>
        </div>

        {/* ----- graphiques ----- */}
        <div className="grid grid-mid">
          <div className="card">
            <h3>Dépenses par catégorie</h3>
            {factures.length ? <Donut parCategorie={stats.parCategorie} total={stats.total} />
              : <div className="vide">Aucune donnée — téléverse ta première facture.</div>}
          </div>
          <div className="card">
            <h3>Dépenses par mois</h3>
            <BarresMensuelles parMois={stats.parMois} />
          </div>
        </div>

        {/* ----- échéances ----- */}
        {stats.echeances.length > 0 && (
          <div className="card">
            <h3>À payer bientôt</h3>
            {stats.echeances.map((f) => (
              <div className="echeance-item" key={f.id}>
                <span>{f.fournisseur ?? "Inconnu"} — {fmt(f.total)}</span>
                <span className="echeance-jours">{joursAvant(f.date_echeance)}</span>
              </div>
            ))}
          </div>
        )}

        {/* ----- dépôt ----- */}
        <div className="card">
          <h3>Ajouter une facture</h3>
          <div className="filtres">
            <button
              className={"btn btn-small" + (portee === "personnel" ? " btn-actif" : "")}
              onClick={() => setPortee("personnel")}>👤 personnel</button>
            <button
              className={"btn btn-small" + (portee === "entreprise" ? " btn-actif" : "")}
              onClick={() => setPortee("entreprise")}>💼 entreprise</button>
            <span style={{ color: "var(--text-dim)", fontSize: "0.75rem" }}>
              la prochaine facture sera classée « {portee} »
            </span>
          </div>
          <label
            className={"dropzone" + (glisse ? " actif" : "")}
            onDragOver={(e) => { e.preventDefault(); setGlisse(true) }}
            onDragLeave={() => setGlisse(false)}
            onDrop={(e) => {
              e.preventDefault()
              setGlisse(false)
              televerser(e.dataTransfer.files[0])
            }}
          >
            {chargement ? "🔮 Extraction en cours..." :
              "Glisse un PDF ou une photo de reçu ici — ou clique pour choisir"}
            <input type="file" accept=".pdf,.jpg,.jpeg,.png"
              onChange={(e) => televerser(e.target.files[0])} />
          </label>
        </div>

        {/* ----- table ----- */}
        <div className="card">
          <h3>Factures</h3>
          <div className="filtres">
            <select className="select-cat" value={filtreCat}
              onChange={(e) => setFiltreCat(e.target.value)}>
              <option value="toutes">toutes les catégories</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select className="select-cat" value={filtreStatut}
              onChange={(e) => setFiltreStatut(e.target.value)}>
              <option value="tous">tous les statuts</option>
              <option value="ok">ok</option>
              <option value="a_valider">à valider</option>
              <option value="doublon_potentiel">doublon potentiel</option>
            </select>
            <select className="select-cat" value={filtrePortee}
              onChange={(e) => setFiltrePortee(e.target.value)}>
              <option value="toutes">personnel + entreprise</option>
              <option value="personnel">👤 personnel</option>
              <option value="entreprise">💼 entreprise</option>
            </select>
            <span style={{ color: "var(--text-dim)", fontSize: "0.75rem", fontFamily: "var(--mono)" }}>
              {facturesAffichees.length} / {factures.length} factures
            </span>
          </div>
          {facturesAffichees.length === 0 ? (
            <div className="vide">Aucune facture ne correspond.</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th className="triable" onClick={() => trierPar("date")}>Date{fleche("date")}</th>
                    <th className="triable" onClick={() => trierPar("fournisseur")}>Fournisseur{fleche("fournisseur")}</th>
                    <th className="triable" onClick={() => trierPar("categorie")}>Catégorie{fleche("categorie")}</th>
                    <th className="triable" onClick={() => trierPar("portee")}>Portée{fleche("portee")}</th>
                    <th className="triable montant" onClick={() => trierPar("total")}>Total{fleche("total")}</th>
                    <th className="triable" onClick={() => trierPar("statut")}>Statut{fleche("statut")}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {facturesAffichees.map((f) => (
                    <tr key={f.id}>
                      <td style={{ fontFamily: "var(--mono)", color: "#94a3b8" }}>{f.date ?? "—"}</td>
                      <td>{f.fournisseur ?? "Inconnu"}</td>
                      <td>
                        <span className="pastille" style={{
                          display: "inline-block", marginRight: 6,
                          background: COULEURS[f.categorie] || COULEURS.autre,
                          color: COULEURS[f.categorie] || COULEURS.autre,
                        }} />
                        <select className="select-cat" value={f.categorie ?? "autre"}
                          onChange={(e) => changerCategorie(f.id, e.target.value)}>
                          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                      </td>
                      <td>
                        <select className="select-cat" value={f.portee ?? "personnel"}
                          onChange={(e) => changerPortee(f.id, e.target.value)}>
                          <option value="personnel">👤 personnel</option>
                          <option value="entreprise">💼 entreprise</option>
                        </select>
                      </td>
                      <td className="montant">{fmt(f.total)}</td>
                      <td><span className={`badge badge-${f.statut}`}>{f.statut}</span></td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                        {f.statut !== "ok" && (
                          <>
                            <button className="btn btn-small" onClick={() => valider(f.id)}>valider</button>{" "}
                            <button className="btn btn-small btn-danger" onClick={() => supprimer(f.id)}>supprimer</button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="actions-bar">
            <a className="btn" href={`${API}/export.csv`}>⬇ Export CSV (impôts / comptabilité)</a>
            <button className="btn" onClick={charger}>↻ Rafraîchir</button>
          </div>
        </div>
      </div>

      {toast && <div className="toast">{toast}</div>}
    </>
  )
}

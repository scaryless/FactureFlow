export default function Landing() {
  return <main className="landing">
    <header className="landing-nav">
      <a className="landing-brand" href="/">FACTURE<span>FLOW</span></a>
      <nav>
        <a href="#fonctionnement">Comment ça marche</a>
        <a href="#securite">Sécurité</a>
        <a className="nav-login" href="?app=1">Se connecter</a>
      </nav>
    </header>

    <section className="landing-hero">
      <div>
        <p className="eyebrow">LA GESTION DE FACTURES, SIMPLIFIÉE</p>
        <h1>Vos factures, enfin <em>en ordre.</em></h1>
        <p className="hero-copy">Déposez une facture. FactureFlow la lit, la classe et vous aide à garder vos dépenses sous contrôle — sans tableur compliqué.</p>
        <div className="hero-actions"><a className="primary-cta" href="?app=1">Commencer gratuitement <span>→</span></a><a className="text-cta" href="#fonctionnement">Voir comment ça marche</a></div>
        <p className="reassurance">Gratuit pour commencer · Aucune carte requise</p>
      </div>
      <aside className="hero-preview" aria-label="Aperçu de FactureFlow">
        <div className="preview-top"><span className="preview-mark">F</span><strong>Vue d’ensemble</strong><span className="preview-period">Ce mois</span></div>
        <div className="preview-stats"><div><small>Dépenses</small><b>2 486,92 $</b><span>↑ toutes tes factures</span></div><div><small>À vérifier</small><b>3</b><span>reçus à confirmer</span></div></div>
        <div className="preview-list"><p>Dernières factures</p><div><i>☕</i><span>Café du Coin<small>Aujourd’hui</small></span><b>12,50 $</b></div><div><i>▣</i><span>Fournitures Bureau<small>Hier</small></span><b>86,20 $</b></div><div><i>↯</i><span>Hydro Québec<small>12 août</small></span><b>143,78 $</b></div></div>
      </aside>
    </section>

    <section id="fonctionnement" className="landing-section"><p className="eyebrow">SIMPLE COMME BONJOUR</p><h2>Trois étapes. Zéro casse-tête.</h2><div className="steps"><article><span>01</span><h3>Déposez</h3><p>Glissez un PDF ou prenez une photo de votre reçu.</p></article><article><span>02</span><h3>FactureFlow lit</h3><p>Les détails sont extraits et classés automatiquement.</p></article><article><span>03</span><h3>Gardez le contrôle</h3><p>Visualisez vos dépenses et exportez-les quand vous en avez besoin.</p></article></div></section>

    <section id="securite" className="security"><div><p className="eyebrow">VOS DONNÉES RESTENT À VOUS</p><h2>Un espace privé, pour chaque personne.</h2><p>Chaque compte voit uniquement ses propres documents. Vous pouvez modifier, exporter ou supprimer vos factures à tout moment.</p></div><div className="security-points"><p>✓ Connexion sécurisée</p><p>✓ Données séparées par compte</p><p>✓ Export CSV pour l’impôt ou votre comptable</p></div></section>

    <section className="landing-final"><p className="eyebrow">PRÊT À SIMPLIFIER VOS PAPIERS ?</p><h2>Commencez avec votre prochaine facture.</h2><a className="primary-cta" href="?app=1">Créer mon espace gratuit <span>→</span></a></section>
    <footer>FactureFlow · Un outil d’Évolution-B</footer>
  </main>
}

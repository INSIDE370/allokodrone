const STEPS = [
  {
    title: "Choisissez votre bowl",
    body: "Poulet, plantains, riz : parcourez la carte et composez votre repas.",
  },
  {
    title: "Retrait ou livraison",
    body: "Passez le prendre au comptoir, ou laissez-le venir jusqu'à votre porte.",
  },
  {
    title: "Dégustez chaud",
    body: "Une cuisine africaine faite maison, servie à grande vitesse.",
  },
] as const;

export function ContactSteps() {
  return (
    <section className="contact-steps" aria-label="Comment commander">
      <ol className="contact-steps-grid">
        {STEPS.map((step, index) => (
          <li key={step.title} className="contact-step">
            <span className="contact-step-num" aria-hidden="true">
              {index + 1}
            </span>
            <h2 className="contact-step-title">{step.title}</h2>
            <p className="contact-step-body">{step.body}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

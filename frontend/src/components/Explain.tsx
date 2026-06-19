import { useState, type ReactNode } from "react";
import { Icon } from "../lib/icons";
import { Modal } from "./ui";

/**
 * Explain — a dual-audience explainer. Inline it reads as a quiet "What does this
 * mean?" affordance for non-technical readers; clicked, it opens a beautiful modal
 * with (1) a plain-English explanation, (2) an optional everyday analogy, and
 * (3) the full technical detail for the technically curious. Same widget, two
 * audiences — nobody is talked down to and nobody is lost.
 */
export function Explain({ title, plain, analogy, children, label = "What does this mean?" }: {
  title: string;
  plain: ReactNode;            // plain-English meaning (always shown)
  analogy?: ReactNode;         // optional everyday analogy callout
  children?: ReactNode;        // the technical detail (revealed under "Under the hood")
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="explain-trigger" onClick={() => setOpen(true)} aria-label={`Explain: ${title}`}>
        <Icon.Info size={13} />
        <span>{label}</span>
      </button>

      <Modal open={open} onClose={() => setOpen(false)} labelledBy="explain-title">
        <div className="explain-modal">
          <div className="explain-head">
            <span className="eyebrow">In plain English</span>
            <h3 id="explain-title" className="serif explain-title">{title}</h3>
          </div>

          <div className="explain-plain">{plain}</div>

          {analogy && (
            <div className="explain-analogy">
              <span className="explain-analogy-ico"><Icon.Info size={15} /></span>
              <div><span className="explain-analogy-tag">Think of it like</span>{analogy}</div>
            </div>
          )}

          {children && (
            <div className="explain-tech">
              <div className="explain-tech-tag">
                <Icon.Brain size={14} /><span>Under the hood — for the technically curious</span>
              </div>
              <div className="explain-tech-body">{children}</div>
            </div>
          )}

          <div className="explain-actions">
            <button className="btn btn-primary btn-sm" onClick={() => setOpen(false)}>
              <Icon.Check size={14} /> Got it
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
}

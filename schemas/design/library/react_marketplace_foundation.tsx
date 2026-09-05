import type { ReactNode } from "react";

export interface MarketplaceFoundationProps {
  readonly title: string;
  readonly children: ReactNode;
  readonly actions?: ReactNode;
}

export function MarketplaceFoundation({
  title,
  children,
  actions,
}: MarketplaceFoundationProps) {
  return (
    <main data-dde-template="marketplace-foundation">
      <header>
        <h1>{title}</h1>
        {actions ? <nav aria-label="Page actions">{actions}</nav> : null}
      </header>
      <section aria-label={title}>{children}</section>
    </main>
  );
}

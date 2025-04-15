declare namespace App {
  interface Locals {
    repsheet?: {
      toc: { items: TocItem[] };
      ogImage?: string | null;
    };
  }
}

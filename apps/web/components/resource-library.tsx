import { ArrowRight, Clock3, Files, Layers3 } from "lucide-react";
import Link from "next/link";

import { learningResources } from "@/lib/editorial-content";

const categories = [
  "Foundations",
  "Practice systems",
  "Reference",
  "Career strategy",
] as const;

export function ResourceLibrary() {
  return (
    <div className="editorial-experience resources-page">
      <header className="resources-hero">
        <div>
          <span>RIGOR REFERENCE LIBRARY</span>
          <h1>
            Practical material for <em>the work between sessions.</em>
          </h1>
          <p>
            Focused guides, checklists, references, and workbooks connected to the
            same practice paths and evidence model used across Rigor.
          </p>
        </div>
        <div className="resources-hero__metrics">
          <div>
            <strong>{learningResources.length}</strong>
            <span>curated resources</span>
          </div>
          <div>
            <strong>{categories.length}</strong>
            <span>working categories</span>
          </div>
          <div>
            <strong>0</strong>
            <span>external trackers</span>
          </div>
        </div>
      </header>

      <main className="resource-groups">
        {categories.map((category, categoryIndex) => {
          const resources = learningResources.filter(
            (resource) => resource.category === category,
          );
          return (
            <section key={category}>
              <header>
                <div>
                  <i>{String(categoryIndex + 1).padStart(2, "0")}</i>
                  <span>{category}</span>
                </div>
                <p>{resources.length} resources</p>
              </header>
              <div className="resource-grid">
                {resources.map((resource) => (
                  <Link href={resource.href} key={resource.title}>
                    <div className="resource-card__meta">
                      <span>
                        {resource.format === "Workbook" ? (
                          <Layers3 size={14} />
                        ) : (
                          <Files size={14} />
                        )}
                        {resource.format}
                      </span>
                      <span>
                        <Clock3 size={12} /> {resource.minutes} min
                      </span>
                    </div>
                    <h2>{resource.title}</h2>
                    <p>{resource.description}</p>
                    <strong>
                      Open resource <ArrowRight size={13} />
                    </strong>
                  </Link>
                ))}
              </div>
            </section>
          );
        })}
      </main>

      <footer className="editorial-taxonomy">
        <span>GUIDES</span>
        <span>CHECKLISTS</span>
        <span>WORKBOOKS</span>
        <span>REFERENCES</span>
      </footer>
    </div>
  );
}

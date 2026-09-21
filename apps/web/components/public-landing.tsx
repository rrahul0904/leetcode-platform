import { ArrowRight, BookOpenCheck, Code2, ShieldCheck, Sparkles, Target } from "lucide-react";
import Link from "next/link";

export function PublicLanding() {
  return (
    <main className="cinematic-page">
      <section className="cinematic-hero" aria-labelledby="skillforge-public-title">
        <div className="cinematic-hero__glow" aria-hidden="true" />
        <div className="cinematic-hero__copy">
          <span className="cinematic-kicker">SKILLFORGE AI · INTERVIEW PREPARATION</span>
          <h1 id="skillforge-public-title">
            Prepare for the interview as a <em>system</em>, not a list of questions.
          </h1>
          <p>
            Practice governed Python, SQL, architecture, code review, and mock-interview
            scenarios while SkillForge turns completed work into evidence-backed readiness.
          </p>
          <div className="cinematic-actions">
            <Link className="cinematic-button cinematic-button--primary" href="/sign-up">
              Create an account <ArrowRight size={16} />
            </Link>
            <Link className="cinematic-button cinematic-button--quiet" href="/sign-in">
              Sign in
            </Link>
          </div>
          <div className="cinematic-proof">
            <span className="cinematic-proof__dot" />
            <span>Governed launch catalog</span>
            <i />
            <span>Isolated execution</span>
            <i />
            <span>Evidence-driven progress</span>
          </div>
        </div>

        <div className="capability-orb" aria-label="SkillForge practice coverage">
          <div className="capability-orb__halo" />
          <div className="capability-orb__sphere">
            <span className="orb-grid orb-grid--one" />
            <span className="orb-grid orb-grid--two" />
            <Sparkles className="orb-core" size={38} />
          </div>
          <div className="capability-orb__caption">
            <span>LAUNCH CATALOG</span>
            <strong>50 governed questions</strong>
          </div>
        </div>
      </section>

      <section className="cinematic-metrics" aria-label="Launch capabilities">
        <article>
          <span>CODING</span>
          <strong>Python + SQL</strong>
          <small>run and submit</small>
        </article>
        <article>
          <span>DESIGN</span>
          <strong>20 cases</strong>
          <small>architecture & systems</small>
        </article>
        <article>
          <span>PRACTICE</span>
          <strong>PR + Arena</strong>
          <small>engineering judgment</small>
        </article>
        <article>
          <span>EVIDENCE</span>
          <strong>Persistent</strong>
          <small>progress and readiness</small>
        </article>
      </section>

      <section className="cinematic-section">
        <div className="cinematic-section__heading">
          <div>
            <span className="cinematic-kicker">BUILT FOR SERIOUS PRACTICE</span>
            <h2>One preparation loop from question to interview evidence.</h2>
          </div>
          <p>
            SkillForge keeps runnable exercises, review practice, system design, and
            interview sessions in one candidate-owned workspace.
          </p>
        </div>

        <div className="cinematic-track-grid">
          <article className="cinematic-track">
            <div className="cinematic-track__top">
              <span>PRACTICE</span>
              <Code2 size={20} />
            </div>
            <h3>Execute real solutions</h3>
            <p>
              Run and submit supported Python and PostgreSQL questions with deterministic
              public and hidden-test evidence.
            </p>
          </article>
          <article className="cinematic-track">
            <div className="cinematic-track__top">
              <span>JUDGMENT</span>
              <Target size={20} />
            </div>
            <h3>Practice beyond algorithms</h3>
            <p>
              Work through architecture cases, PR reviews, AI Arena challenges, and
              structured mock interviews.
            </p>
          </article>
          <article className="cinematic-track">
            <div className="cinematic-track__top">
              <span>TRUST</span>
              <ShieldCheck size={20} />
            </div>
            <h3>Know what the score means</h3>
            <p>
              Candidate data stays isolated, content is rights-checked, and progress is
              backed by durable evidence instead of demo counters.
            </p>
          </article>
        </div>
      </section>

      <section className="cinematic-section cinematic-section--split">
        <div className="cinematic-manifesto">
          <span className="cinematic-kicker">START WITH A FOCUSED BANK</span>
          <h2>Launch small enough to trust, broad enough to practice.</h2>
          <p>
            The initial bank contains 20 Python, 10 SQL, and 20 architecture/design
            packages. We expand only through the same schema, rights, validation, and
            publication controls.
          </p>
        </div>
        <div className="cinematic-recent">
          <div className="cinematic-recent__heading">
            <span>READY WHEN YOU ARE</span>
            <BookOpenCheck size={18} />
          </div>
          <Link href="/sign-up">
            <span className="cinematic-recent__number">01</span>
            <div>
              <strong>Create your candidate profile</strong>
              <small>Set target role, priorities, and study intensity.</small>
            </div>
            <ArrowRight size={15} />
          </Link>
          <Link href="/sign-in">
            <span className="cinematic-recent__number">02</span>
            <div>
              <strong>Return to your workspace</strong>
              <small>Continue from durable submissions and readiness evidence.</small>
            </div>
            <ArrowRight size={15} />
          </Link>
        </div>
      </section>
    </main>
  );
}

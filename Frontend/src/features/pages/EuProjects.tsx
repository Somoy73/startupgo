import { ArrowLeft } from "lucide-react";
import { CordisWidget } from "../../components/CordisWidget";
import { Link } from "../../lib/navigation";

export function EuProjects() {
  return (
    <div className="landing">
      <div className="page-head">
        <div>
          <h1>EU ocean projects</h1>
          <p>Blue-economy projects funded by the EU, from CORDIS.</p>
        </div>
      </div>
      <section className="dash-card" aria-labelledby="eu-projects-heading">
        <div className="dash-card-head">
          <h2 id="eu-projects-heading">Latest projects</h2>
          <Link to="/" className="dash-more">
            <ArrowLeft /> Back home
          </Link>
        </div>
        <CordisWidget output="table" />
      </section>
    </div>
  );
}

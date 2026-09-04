import { Hero } from "@/components/landing/Hero";
import {
  Checks,
  DestinationReadiness,
  FinalCall,
  LandingFooter,
  Workflow,
} from "@/components/landing/Sections";

/**
 * The public landing page.
 *
 * A static-first editorial page. The authenticated workspace lives on its own
 * routes and does not share these presentation components.
 */
export default function Home() {
  return (
    <main id="main">
      <Hero />
      <Workflow />
      <Checks />
      <DestinationReadiness />
      <FinalCall />
      <LandingFooter />
    </main>
  );
}

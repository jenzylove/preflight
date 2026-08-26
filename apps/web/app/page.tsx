import { Hero, HeroStatic } from "@/components/landing/Hero";
import {
  CurrentRequirements,
  EveryDeliveryKeepsItsEvidence,
  FinalCall,
  LandingFooter,
  MeasureNeverGuess,
  OneMasterManyDestinations,
  SafeRepairsStaySafe,
} from "@/components/landing/Sections";

/**
 * The public landing page.
 *
 * The hero is a scroll-driven sequence; everything below it is static. Both
 * are rendered, and CSS decides which hero the viewer gets — the animated one
 * by default, the static exploded diagram when motion is reduced. Doing that
 * in CSS rather than JavaScript means the correct version is present in the
 * very first paint, with no flash of the wrong one.
 */
export default function Home() {
  return (
    <main id="main">
      <Hero />
      <HeroStatic />
      <OneMasterManyDestinations />
      <CurrentRequirements />
      <MeasureNeverGuess />
      <SafeRepairsStaySafe />
      <EveryDeliveryKeepsItsEvidence />
      <FinalCall />
      <LandingFooter />
    </main>
  );
}

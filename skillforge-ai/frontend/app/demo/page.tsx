import type { Metadata } from "next";
import { InteractiveDemo } from "@/components/interactive-demo";

export const metadata: Metadata = {
  title: "Interactive Demo | SkillForge AI",
  description: "Interactive SkillForge AI preview for data engineering interview preparation.",
};

export default function DemoPage() {
  return <InteractiveDemo/>;
}

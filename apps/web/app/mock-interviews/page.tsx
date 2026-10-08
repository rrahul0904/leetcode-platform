import Link from "next/link";

import { MockInterviewWorkspace } from "@/components/mock-interview-workspace";

export default function MockInterviewsPage() {
  return (
    <>
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          padding: "14px 18px 0",
          background: "#080a0f",
        }}
      >
        <Link
          href="/think-aloud"
          style={{
            border: "1px solid rgba(126, 130, 255, 0.3)",
            borderRadius: 999,
            padding: "9px 14px",
            color: "#b7baff",
            fontSize: 13,
            fontWeight: 700,
            textDecoration: "none",
          }}
        >
          Try Think Aloud voice + system-design interviews →
        </Link>
      </div>
      <MockInterviewWorkspace />
    </>
  );
}

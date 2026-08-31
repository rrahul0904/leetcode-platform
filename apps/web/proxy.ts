import { clerkMiddleware } from "@clerk/nextjs/server";
import type { NextFetchEvent, NextRequest } from "next/server";
import { NextResponse } from "next/server";

const clerkProxy = clerkMiddleware();
const authMode =
  process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE ??
  (process.env.NODE_ENV === "production" ? "clerk" : "local");

export default function proxy(request: NextRequest, event: NextFetchEvent) {
  if (authMode !== "clerk") {
    return NextResponse.next();
  }
  return clerkProxy(request, event);
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
    "/__clerk/(.*)",
  ],
};

import { NextResponse, type NextRequest } from "next/server";

/**
 * Auth middleware — redirects unauthenticated users away from /app/*.
 * Cookie-level check only (fast, no DB hit). Backend API enforces tier gates
 * independently so this is defence-in-depth, not the sole gate.
 */
export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const isAppRoute = pathname.startsWith("/app");
  if (!isAppRoute) return NextResponse.next();

  const session = request.cookies.get("tapeline_session")?.value;
  if (!session) {
    const signinUrl = new URL("/signin", request.url);
    signinUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(signinUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/app/:path*"],
};

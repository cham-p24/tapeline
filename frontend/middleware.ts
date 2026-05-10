import { NextResponse, type NextRequest } from "next/server";

/**
 * Edge middleware. Two responsibilities, in order:
 *   1. Serve the IndexNow key file dynamically at /<INDEXNOW_KEY>.txt
 *      so the key lives in env vars (no git history exposure) and we
 *      avoid a top-level catch-all route conflicting with static pages.
 *   2. Auth redirect for /app/* — cookie-only check, defence-in-depth
 *      with backend tier gates.
 *
 * The matcher below covers both surfaces. Single-segment hex .txt
 * requests hit the IndexNow path; everything under /app/* hits auth.
 */
export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  // IndexNow key verification. Spec requires the file at
  //   https://<host>/<KEY>.txt
  // with the key as plaintext content. The regex narrows to hex
  // strings 8-128 chars long so legitimate .txt files (robots.txt,
  // ads.txt, etc.) never collide here.
  const indexnowMatch = pathname.match(/^\/([a-f0-9]{8,128})\.txt$/i);
  if (indexnowMatch) {
    const key = process.env.INDEXNOW_KEY;
    if (key && indexnowMatch[1] === key) {
      return new NextResponse(key, {
        status: 200,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "Cache-Control": "public, max-age=3600",
        },
      });
    }
    // Anything matching the .txt key shape but NOT our key gets a
    // clean 404 rather than a generic Next.js page.
    return new NextResponse("Not Found", { status: 404 });
  }

  // Auth redirect for /app/*.
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
  // Match /app/* (auth) AND any single-segment hex .txt path (IndexNow).
  matcher: ["/app/:path*", "/:key([a-fA-F0-9]{8,128}).txt"],
};

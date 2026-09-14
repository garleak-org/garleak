import { NextResponse, type NextRequest } from "next/server";

/**
 * Nothing ever 404s (or 500s) for an archive identifier. Next.js fails with a 500
 * when a path carries a malformed percent-escape such as /abs/%E0%A4%A, before any
 * page code runs. Escape every % in such a path and redirect, so the page receives
 * the raw text and can render its "not a Garleak identifier" state.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  try {
    decodeURIComponent(pathname);
    return NextResponse.next();
  } catch {
    const url = request.nextUrl.clone();
    url.pathname = pathname.replaceAll("%", "%25");
    return NextResponse.redirect(url, 308);
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

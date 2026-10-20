import { proxyAuthRequest } from "@/lib/server/auth-api";

export async function POST(request: Request): Promise<Response> {
  return proxyAuthRequest(request, "register");
}

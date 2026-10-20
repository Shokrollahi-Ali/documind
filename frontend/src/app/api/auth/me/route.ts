import { proxyAuthRequest } from "@/lib/server/auth-api";

export async function GET(request: Request): Promise<Response> {
  return proxyAuthRequest(request, "me");
}

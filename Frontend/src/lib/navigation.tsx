import {
  Link as RouterLink,
  useLocation,
  useNavigate as useRouterNavigate,
  useParams as useRouterParams,
} from "@tanstack/react-router";
import type { ReactNode, MouseEventHandler } from "react";
export function Link({
  to,
  ...props
}: {
  to: string;
  children: ReactNode;
  className?: string;
  onClick?: MouseEventHandler<HTMLAnchorElement>;
}) {
  return <RouterLink to={to} {...props} />;
}
export function useNavigate() {
  const navigate = useRouterNavigate();
  return (path: string) => navigate({ to: path });
}
export function useParams() {
  return useRouterParams({ strict: false }) as { slug?: string };
}
export function useSearchParams() {
  const location = useLocation();
  const navigate = useRouterNavigate();
  const params = new URLSearchParams(location.searchStr);
  const set = (next: URLSearchParams | Record<string, string>, options?: { replace?: boolean }) =>
    navigate({
      to: location.pathname,
      search: Object.fromEntries(
        next instanceof URLSearchParams ? next.entries() : Object.entries(next),
      ),
      replace: options?.replace ?? false,
    });
  return [params, set] as const;
}

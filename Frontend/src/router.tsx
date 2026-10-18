import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";

export const getRouter = () => {
  const queryClient = new QueryClient();

  const router = createRouter({
    routeTree,
    context: { queryClient },
    scrollRestoration: true,
    // The browser cross-fades between pages where it supports View Transitions (styles.css, Motion).
    defaultViewTransition: true,
    defaultPreloadStaleTime: 0,
  });

  return router;
};

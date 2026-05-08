import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRootRoute, createRoute, createRouter, Outlet, RouterProvider } from "@tanstack/react-router";
import React from "react";
import ReactDOM from "react-dom/client";
import { AdminConsole, ProductPage } from "./App";
import type { ProductPageId } from "./App";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1
    }
  }
});

const rootRoute = createRootRoute({
  component: () => <Outlet />
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => <ProductPage caseId="CASE-CAMPUS-001" page="risk" />
});

const productRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/cases/$caseId/$page",
  component: function ProductRoute() {
    const params = productRoute.useParams();
    return <ProductPage caseId={params.caseId} page={params.page as ProductPageId} />;
  }
});

const adminRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin",
  component: AdminConsole
});

const routeTree = rootRoute.addChildren([indexRoute, productRoute, adminRoute]);
const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>
);

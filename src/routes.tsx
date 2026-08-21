import type { RouteObject } from 'react-router';

import App from './App';
import Home from './routes/home';
import Settings from './routes/settings/index';
import { ProtectedRoute } from './routes/protected-route';

const routes = [
  {
    path: '/',
    Component: App,
    children: [
      {
        index: true,
        Component: Home,
      },
      {
        path: 'settings',
        element: (
          <ProtectedRoute>
            <Settings />
          </ProtectedRoute>
        ),
      },
    ],
  },
] satisfies RouteObject[];

export { routes };

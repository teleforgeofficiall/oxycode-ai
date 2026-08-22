import type { RouteObject } from 'react-router';
import { Navigate } from 'react-router';

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
        path: 'profile',
        element: (
          <ProtectedRoute>
            <Settings />
          </ProtectedRoute>
        ),
      },
      {
        path: 'settings',
        element: <Navigate to="/profile" replace />,
      },
    ],
  },
] satisfies RouteObject[];

export { routes };

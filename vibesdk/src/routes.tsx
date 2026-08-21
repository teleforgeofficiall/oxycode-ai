import type { RouteObject } from 'react-router';

import App from './App';
import Home from './routes/home';
import Profile from './routes/settings/index';
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
            <Profile />
          </ProtectedRoute>
        ),
      },
      {
        path: '*',
        Component: Home,
      },
    ],
  },
] satisfies RouteObject[];

export { routes };

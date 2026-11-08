import {retryRouteImports} from "@/lib/lazy-route";
import React from "react";
import { recoverChunkLoad } from "@/lib/chunk-recovery";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type ErrorBoundaryState = {
  hasError: boolean;
};

export default class ErrorBoundary extends React.Component<React.PropsWithChildren<{resetKey?:string}>, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidUpdate(previous: React.PropsWithChildren<{resetKey?:string}>) {
    if (this.state.hasError && previous.resetKey !== this.props.resetKey) this.setState({hasError:false});
  }

  componentDidCatch(error: Error) {
    recoverChunkLoad(error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Card className="mx-auto mt-10 max-w-lg">
          <CardHeader>
            <CardTitle>Something went wrong</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">The page could not be rendered. Retry here or open another page.</p>
            <Button onClick={() => {retryRouteImports();this.setState({hasError:false});}}>Retry page</Button>
            <Button variant="outline" onClick={() => window.location.reload()}>Reload application</Button>
          </CardContent>
        </Card>
      );
    }

    return this.props.children;
  }
}

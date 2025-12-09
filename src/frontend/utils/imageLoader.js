// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

export default function imageLoader({ src, width, quality }) {
  src = src.replace(/^\/+/, ''); // strip any leading slashes since it's already defined in the string below
  // We pass down the optimisation request to the image-provider service here, without this, nextJs would try to use internal optimiser which is not working with the external image-provider.
  return `/${src}?w=${width}&q=${quality || 75}`;
}

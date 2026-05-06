// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Link from 'next/link';
import { useState, useEffect } from 'react';
import * as S from './Banner.styled';

const Banner = () => {
  const [imageSrc, setImageSrc] = useState<string>('');

  useEffect(() => {
    fetch('/api/images/Banner.png')
      .then(res => res.blob())
      .then(blob => setImageSrc(URL.createObjectURL(blob)));
  }, []);

  return (
    <S.Banner>
      <S.ImageContainer>
        {/* data-cy="banner-img" lets Playwright (locust) wait for the banner to
            finish loading before interacting with the page. */}
        <S.BannerImg src={imageSrc} data-cy="banner-img" />
      </S.ImageContainer>
      <S.TextContainer>
        <S.Title>The best telescopes to see the world closer</S.Title>
        <Link href="#hot-products">
          <S.GoShoppingButton>Go Shopping</S.GoShoppingButton>
        </Link>
      </S.TextContainer>
    </S.Banner>
  );
};

export default Banner;

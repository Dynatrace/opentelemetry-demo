// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import styled from 'styled-components';
import Button from '../Button';

export const CheckoutForm = styled.form``;

export const StateRow = styled.div`
  display: grid;
  grid-template-columns: 35% 55%;
  gap: 10%;
`;

export const Title = styled.h1`
  margin: 0;
  margin-bottom: 24px;
`;

export const CardRow = styled.div`
  display: grid;
  grid-template-columns: 35% 35% 20%;
  gap: 5%;
`;

export const SubmitContainer = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px;
  flex-direction: column-reverse;

  ${({ theme }) => theme.breakpoints.desktop} {
    flex-direction: row;
    justify-content: end;
    align-items: center;
    margin-top: 67px;
  }
`;

export const CartButton = styled(Button)`
  padding: 16px 35px;
  font-weight: ${({ theme }) => theme.fonts.regular};
  width: 100%;

  ${({ theme }) => theme.breakpoints.desktop} {
    width: inherit;
  }
`;

export const EmptyCartButton = styled(Button)`
  font-weight: ${({ theme }) => theme.fonts.regular};
  color: ${({ theme }) => theme.colors.otelRed};
  width: 100%;

  ${({ theme }) => theme.breakpoints.desktop} {
    width: inherit;
  }
`;

export const ErrorWrapper = styled.div`
  margin-bottom: 16px;
`;

export const ErrorHeading = styled.h1`
  margin: 8px 0 4px;
`;

export const ErrorSubtitle = styled.p`
  margin: 0 0 12px;
  color: ${({ theme }) => theme.colors.textLightGray};
`;

export const ErrorMessage = styled.div`
  color: ${({ theme }) => theme.colors.otelRed};
  font-size: 1.1rem;
`;

export const ErrorStack = styled.pre`
  margin: 6px 0 0;
  font-size: 0.8rem;
  white-space: pre-wrap;
  word-break: break-all;
  opacity: 0.8;
  color: ${({ theme }) => theme.colors.otelRed};
`;

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { InferGetServerSidePropsType, NextPage } from 'next';
import Head from 'next/head';
import Footer from '../../components/Footer';
import Layout from '../../components/Layout';
import Recommendations from '../../components/Recommendations';
import * as S from '../../styles/Cart.styled';
import CartDetail from '../../components/Cart/CartDetail';
import EmptyCart from '../../components/Cart/EmptyCart';
import { useCart } from '../../providers/Cart.provider';
import AdProvider from '../../providers/Ad.provider';
import { getCookie } from 'cookies-next';

export async function getServerSideProps() {
  const userId = getCookie('USERID') as string;

  return {
    props: { userId },
  };
}

const Cart: NextPage<InferGetServerSidePropsType<typeof getServerSideProps>> = ({ userId }) => {
  const {
    cart: { items },
  } = useCart();

  return (
    <AdProvider
      productIds={items.map(({ productId }) => productId)}
      contextKeys={[...new Set(items.flatMap(({ product }) => product.categories))]}
    >
      <Head>
        <title>Otel Demo - Cart</title>
      </Head>
      <Layout>
        <S.Cart>
          {(!!items.length && <CartDetail userId={userId} />) || <EmptyCart />}
          <Recommendations />
        </S.Cart>
        <Footer userId={userId} />
      </Layout>
    </AdProvider>
  );
};

export default Cart;

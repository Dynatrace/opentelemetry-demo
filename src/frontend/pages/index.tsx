// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { InferGetServerSidePropsType, NextPage } from 'next';
import Head from 'next/head';
import Footer from '../components/Footer';
import Layout from '../components/Layout';
import ProductList from '../components/ProductList';
import * as S from '../styles/Home.styled';
import { useQuery } from '@tanstack/react-query';
import ApiGateway from '../gateways/Api.gateway';
import Banner from '../components/Banner';
import { CypressFields } from '../utils/enums/CypressFields';
import { useCurrency } from '../providers/Currency.provider';
import { getCookie } from 'cookies-next';

export async function getServerSideProps() {
  const userId = getCookie('USERID') as string;

  return {
    props: { userId },
  };
}

const Home: NextPage<InferGetServerSidePropsType<typeof getServerSideProps>> = ({ userId }) => {
  const { selectedCurrency } = useCurrency();
  const { data: productList = [] } = useQuery({
    queryKey: ['products', selectedCurrency],
    queryFn: () => ApiGateway.listProducts(selectedCurrency),
  });

  return (
    <Layout>
      <Head>
        <title>Otel Demo - Home</title>
      </Head>
      <S.Home data-cy={CypressFields.HomePage}>
        <Banner />
        <S.Container>
          <S.Row>
            <S.Content>
              <S.HotProducts>
                <S.HotProductsTitle data-cy={CypressFields.HotProducts} id="hot-products">
                  Hot Products
                </S.HotProductsTitle>
                <ProductList productList={productList} />
              </S.HotProducts>
            </S.Content>
          </S.Row>
        </S.Container>
        <Footer userId={userId} />
      </S.Home>
    </Layout>
  );
};

export default Home;

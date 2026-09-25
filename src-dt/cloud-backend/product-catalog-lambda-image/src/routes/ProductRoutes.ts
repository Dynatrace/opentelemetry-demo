import express, { NextFunction, Request, Response, Router } from 'express';
import { Translations } from 'services/Translations';
import { Database } from 'services/Database';

export default class ProductRoutes {
  public router: Router;
  private database: Database;
  private translations: Translations;

  constructor(database: Database, translations: Translations) {
    this.router = express.Router();
    this.database = database;
    this.translations = translations;
    this.registerRoutes();
  }

  protected registerRoutes(): void {
    // Setup express Routes
    this.router.get('/', this.getAllProducts.bind(this));
    this.router.get('/:key', this.getProduct.bind(this));
    this.router.post('/', this.addProduct.bind(this));
    this.router.put('/:key', this.updateProduct.bind(this));
    this.router.delete('/:key', this.deleteProduct.bind(this));
  }

  private async getAllProducts(req: Request, res: Response, next: NextFunction) {
    req.log.info('GET /db/product');
    const state = await this.database.ProductState.findAll();
    req.log.debug(state);
    // Call the repository to get the product
    return res.json(state.map((s: any) => s.value));
  }

  private async getProduct(req: Request, res: Response, next: NextFunction) {
    const key = req.params.key?.toString();

    if (!key) {
      req.log.warn('KEY is required');
      return res.status(400).send('KEY is required');
    }

    req.log.info('GET /db/product/:key', req.params.key);
    const state = await this.database.ProductState.findByPk(key);
    // Call the repository to get the product
    return res.json(state ? state.value : null);
  }

  private async addProduct(req: Request, res: Response, next: NextFunction) {
    const product = req.body;
    if (product) {
      req.log.info('POST /db/product', product);
      const addedState = await this.database.ProductState.create({ key: product.id, value: product });
      if (product.description) {
        req.log.info('Product description added', product.description);
        await this.translations.requestTranslation(product.id, [{ name: "description", value: product.description }]);
      }
      else
        req.log.info('Product description not added');
    }
    else
      req.log.warn('POST /db/product', 'No product data in request');
    return res.send('OK');
  }

  private async updateProduct(req: Request, res: Response, next: NextFunction) {
    const key = req.params.key?.toString();

    if (!key) {
      req.log.warn('KEY is required');
      return res.status(400).send('KEY is required');
    }

    req.log.info('PUT /db/product/:key', key);
    const product = req.body;
    if (product) {
      req.log.debug('request payload', key, product);
      await this.database.ProductState.update({ value: product }, { where: { key: key } });
      if (product.description) {
        req.log.info('Product description updated', product.description);
        await this.translations.requestTranslation(key, [{ name: "description", value: product.description }]);
      }
      else
        req.log.info('Product description not updated', key);
    }
    else
      req.log.warn('PUT /db/product/:key', 'No product data in request');

    return res.send('OK');
  }

  private async deleteProduct(req: Request, res: Response, next: NextFunction) {
    const key = req.params.key?.toString();

    if (!key) {
      req.log.warn('KEY is required');
      return res.status(400).send('KEY is required');
    }

    console.info('DELETE /db/product/:key', req.params.key);
    await this.database.ProductState.destroy({
      where: {
        key: key,
      },
    });
    return res.send('OK');
  }
}

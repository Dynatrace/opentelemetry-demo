import express, { NextFunction, Request, Response, Router } from 'express';
import { Translations } from 'services/Translations';
import { Database } from 'services/Database';

export default class ProductV2Routes {
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
    this.router.get('/:id', this.getProduct.bind(this));
    this.router.post('/', this.addProduct.bind(this));
    this.router.put('/:id', this.updateProduct.bind(this));
    this.router.delete('/:id', this.deleteProduct.bind(this));
  }

  private async getAllProducts(req: Request, res: Response, next: NextFunction) {
    req.log.info('GET /db/v2/product');
    const products = await this.database.Product.findAll();
    req.log.debug(products);
    // Call the repository to get the product
    return res.json(products);
  }

  private async getProduct(req: Request, res: Response, next: NextFunction) {
    const id = req.params.id?.toString();

    if (!id) {
      req.log.warn('ID is required');
      return res.status(400).send('ID is required');
    }

    req.log.info('GET /db/v2/product/:id', req.params.id);
    const product = await this.database.Product.findByPk(id);
    // Call the repository to get the product
    return res.json(product);
  }

  private async addProduct(req: Request, res: Response, next: NextFunction) {
    const product = req.body;
    if (product) {
      req.log.info('POST /db/v2/product', product);
      const addedProduct = await this.database.Product.create(product);
      if (product.description) {
        req.log.info('Product description added', product.description);
        await this.translations.requestTranslation(product.id, [{ name: "description", value: product.description }]);
      }
      else
        req.log.info('Product description not added');
    }
    else
      req.log.warn('POST /db/v2/product', 'No product data in request');
    return res.send('OK');
  }

  private async updateProduct(req: Request, res: Response, next: NextFunction) {
    const id = req.params.id?.toString();

    if (!id) {
      req.log.warn('ID is required');
      return res.status(400).send('ID is required');
    }

    req.log.info('PUT /db/v2/product/:id', id);
    const product = req.body;
    if (product) {
      req.log.debug('request payload', id, product);
      await this.database.Product.update(product, { where: { id: id } });
      if (product.description) {
        req.log.info('Product description updated', product.description);
        await this.translations.requestTranslation(id, [{ name: "description", value: product.description }]);
      }
      else
        req.log.info('Product description not updated', id);
    }
    else
      req.log.warn('PUT /db/v2/product/:id', 'No product data in request');

    return res.send('OK');
  }

  private async deleteProduct(req: Request, res: Response, next: NextFunction) {
    const id = req.params.id?.toString();

    if (!id) {
      req.log.warn('ID is required');
      return res.status(400).send('ID is required');
    }

    console.info('DELETE /db/v2/product/:id', req.params.id);
    await this.database.Product.destroy({
      where: {
        id: id,
      },
    });
    return res.send('OK');
  }
}

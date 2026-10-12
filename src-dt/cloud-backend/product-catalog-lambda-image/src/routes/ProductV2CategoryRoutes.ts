import express, { NextFunction, Request, Response, Router } from 'express';
import { Database } from 'services/Database';

export default class ProductCategoryV2Routes {
  public router: Router;
  private database: Database;

  constructor(database: Database) {
    this.router = express.Router();
    this.database = database;
    this.registerRoutes();
  }

  protected registerRoutes(): void {
    // Setup express Routes
    this.router.get('/', this.getAllProductCategories.bind(this));
    this.router.get('/:id', this.getProductCategory.bind(this));
    this.router.post('/', this.addProductCategory.bind(this));
    this.router.put('/:id', this.updateProductCategory.bind(this));
    this.router.delete('/:id', this.deleteProductCategory.bind(this));
  }

  private async getAllProductCategories(req: Request, res: Response, next: NextFunction) {
    req.log.info('GET /db/v2/product-category');
    const products = await this.database.ProductCategory.findAll();
    req.log.debug(products);
    // Call the repository to get the product
    return res.json(products);
  }

  private async getProductCategory(req: Request, res: Response, next: NextFunction) {
    const id = req.params.id?.toString();

    if (!id) {
      req.log.warn('ID is required');
      return res.status(400).send('ID is required');
    }

    req.log.info('GET /db/v2/product-category/:id', req.params.id);
    const product = await this.database.ProductCategory.findByPk(id);
    // Call the repository to get the product-category
    return res.json(product);
  }

  private async addProductCategory(req: Request, res: Response, next: NextFunction) {
    const category = req.body;
    if (category) {
      req.log.info('POST /db/v2/product-category', category);
      await this.database.ProductCategory.create(category);
    }
    else
      req.log.warn('POST /db/v2/product-category', 'No product-category data in request');
    return res.send('OK');
  }

  private async updateProductCategory(req: Request, res: Response, next: NextFunction) {
    const id = req.params.id?.toString();

    if (!id) {
      req.log.warn('ID is required');
      return res.status(400).send('ID is required');
    }

    req.log.info('PUT /db/v2/product-category/:id', id);
    const category = req.body;
    if (category) {
      req.log.debug('request payload', id, category);
      await this.database.ProductCategory.update(category, { where: { id: id } });
    }
    else
      req.log.warn('PUT /db/v2/product-category/:id', 'No product-category data in request');

    return res.send('OK');
  }

  private async deleteProductCategory(req: Request, res: Response, next: NextFunction) {
    const id = req.params.id?.toString();

    if (!id) {
      req.log.warn('ID is required');
      return res.status(400).send('ID is required');
    }

    console.info('DELETE /db/v2/product-category/:id', req.params.id);
    await this.database.ProductCategory.destroy({
      where: {
        id: id,
      },
    });
    return res.send('OK');
  }

}

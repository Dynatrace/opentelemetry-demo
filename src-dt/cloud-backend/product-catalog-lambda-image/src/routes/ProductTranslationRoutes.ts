import express, { NextFunction, Request, Response, Router } from 'express';
import { Database } from 'services/Database';

export default class ProductTranslationRoutes {
  public router: Router;
  private database: Database;

  constructor(database: Database) {
    this.router = express.Router();
    this.database = database;
    this.registerRoutes();
  }

  protected registerRoutes(): void {
    // Setup express Routes
    this.router.get('/', this.getAllProductTranslations.bind(this));
    this.router.get('/:id', this.getProductTranslation.bind(this));
    this.router.post('/', this.addProductTranslation.bind(this));
    this.router.put('/:id', this.updateProductTranslation.bind(this));
    this.router.delete('/:id', this.deleteProductTranslation.bind(this));
  }

  private async getAllProductTranslations(req: Request, res: Response, next: NextFunction) {
    req.log.info('POST /product-translations');
    const translations = await this.database.ProductTranslation.findAll();
    req.log.debug(JSON.stringify(translations));
    // Call the repository to get the product
    return res.json(translations);
  }

  private async getProductTranslation(req: Request, res: Response, next: NextFunction) {
    const id = req.params.id?.toString();

    if (!id) {
      req.log.warn('ID is required');
      return res.status(400).send('ID is required');
    }
    req.log.info('GET /product-translation/:id', req.params.id);
    const translation = await this.database.ProductTranslation.findByPk(id);
    // Call the repository to get the product
    return res.json(translation);
  }

  private async addProductTranslation(req: Request, res: Response, next: NextFunction) {
    const translation = req.body;
    if (translation) {
      req.log.info('POST /db/product-translation', translation);
      await this.database.ProductTranslation.create(translation);
    }
    else
      req.log.warn('POST /db/product-translation', 'No product-translation data in request');
    return res.send('OK');
  }

  private async updateProductTranslation(req: Request, res: Response, next: NextFunction) {
    const id = req.params.id?.toString();

    if (!id) {
      req.log.warn('ID is required');
      return res.status(400).send('ID is required');
    }

    req.log.info('PUT /db/product-translation/:id', id);
    const translation = req.body;
    if (translation) {
      req.log.debug('request payload', id, translation);
      await this.database.ProductTranslation.update(translation, { where: { id: id } });
    }
    else
      req.log.warn('PUT /db/product-translation/:id', 'No product-translation data in request');

    return res.send('OK');
  }

  private async deleteProductTranslation(req: Request, res: Response, next: NextFunction) {
    const id = req.params.id?.toString();

    if (!id) {
      req.log.warn('ID is required');
      return res.status(400).send('ID is required');
    }

    console.info('DELETE /db/product-translation/:id', req.params.id);
    await this.database.ProductTranslation.destroy({
      where: {
        id: id,
      },
    });
    return res.send('OK');
  }
}
